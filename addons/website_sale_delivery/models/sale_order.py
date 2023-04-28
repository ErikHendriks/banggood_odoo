# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging

import requests
from requests.structures import CaseInsensitiveDict

from odoo import api, fields, models
from odoo.addons.website_sale_delivery.controllers.bggat import GAT

_logger = logging.getLogger(__name__)




with open("/PATH/addons/website_sale_delivery/controllers/.access_token") as f:
    access_token = f.read()

# base_url = "https://api.banggood.com"
params = {"lang": "en", "access_token": access_token}


def make_get_request(url: str, params: dict) -> object:

    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"
    headers["Connection"] = "close"

    # params["access_token"] = GAT.get_access_token()
    response = requests.get(url, params=params, headers=headers)
    response = json.loads(response.text)

    if response["code"] == 21020 or response["code"] == 21030 or response["code"] == 11020:

        # print(response)
        params["access_token"] = GAT.get_access_token()
        response = requests.get(url=url, params=params, headers=headers)
        response = json.loads(response.text)

        return response

    elif response["code"] == 31020:

        # print(response)
        print("make_get_request(SALE_ORDER) " + str(response), file=open('PATH', 'a'))
        return 0

    return response


def get_shipment(order):
    # order = request.website.sale_get_order()
    # print(len(order.order_line))

    # params = {"lang": "en"}
    # params["access_token"] = access_token
    url = "https://api.banggood.com/product/getShipments"

    shipment = {"4": "Sorry, no shipment to this country. Please contact us for an solution.",
                "5": "Sorry, no shipment to this country. Please contact us for an solution."}

    # country
    # print(order.partner_shipping_id.country_code)
    for line in order.order_line:
        print("line")
        # print(line)
        if line.product_id.default_code:
            # quantity
            # print(line.product_qty)
            # warehouse
            # print(str(line.warehouse_id.code))
            # product_id
            # print(str(line.product_id.default_code))
            #
            # print("request")
            params["product_id"] = str(line.product_id.default_code)
            # params["product_id"] = "1593136"
            # params["warehouse"] = line.warehouse_id.code
            params["warehouse"] = "CN"
            if order.partner_shipping_id.country_code == "BE":
                country = "Belgium"
            else:
                country = "Belgium"
            params["country"] = country
            # params["country"] = "Belgium"
            # params["poa_id"] = ""
            params["quantity"] = int(line.product_qty)
            params["currency"] = "USD"

            response = make_get_request(url, params)
            # response = {
            #
            #     "code": 0,
            #
            #     "currency": "USD",
            #
            #     "shipmethod_list": [
            #
            #         {
            #
            #             "shipment_code": "ecoship",
            #
            #             "shipment_name": "Expedited Shipping Service1",
            #
            #             "shipday": "5-8 business days",
            #
            #             "shipfee": "40.00"
            #
            #         },
            #
            #         {
            #
            #             "shipment_code": "prioship",
            #
            #             "shipment_name": "Expedited Shipping Service2",
            #
            #             "shipday": "5-8 business days",
            #
            #             "shipfee": "0.00"
            #
            #         },
            #
            #         {
            #
            #             "shipment_code": "cndhl_cndhl3",
            #
            #             "shipment_name": "Expedited Shipping Service3",
            #
            #             "shipday": "5-8 business days",
            #
            #             "shipfee": "10.92"
            #
            #         },
            #     ],
            #
            #     "lang": "en"
            #
            # }
            # print(response)

            if "shipmethod_list" not in response:
                print("get_shipment(SALE_ORDER) " + str(response), file=open('PATH', 'a'))
            fee = []

            if "shipmethod_list" in response:
                for i in response["shipmethod_list"]:
                    fee.append(float(i["shipfee"]))

            # print(fee)
            fee.sort()

            if len(fee) == 1:
                if type(shipment["4"]) == str:
                    shipment["4"] = fee[0]
                    shipment["5"] = fee[0]
                else:
                    shipment["4"] += fee[0]
                    shipment["5"] += fee[0]
            elif len(fee) > 1:
                if type(shipment["4"]) == str:
                    shipment["4"] = fee[0]
                    shipment["5"] = fee[1]
                else:
                    shipment["4"] += fee[0]
                    shipment["5"] += fee[1]

    # print(json.dumps(shipment, indent=4, sort_keys=True))
    return shipment


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    amount_delivery = fields.Monetary(
        compute='_compute_amount_delivery',
        string='Delivery Amount',
        help="The amount without tax.", store=True, tracking=True)

    def _compute_website_order_line(self):
        super(SaleOrder, self)._compute_website_order_line()
        for order in self:
            order.website_order_line = order.website_order_line.filtered(lambda l: not l.is_delivery)

    @api.depends('order_line.price_unit', 'order_line.tax_id', 'order_line.discount', 'order_line.product_uom_qty')
    def _compute_amount_delivery(self):
        for order in self:
            if self.env.user.has_group('account.group_show_line_subtotals_tax_excluded'):
                order.amount_delivery = sum(order.order_line.filtered('is_delivery').mapped('price_subtotal'))
            else:
                order.amount_delivery = sum(order.order_line.filtered('is_delivery').mapped('price_total'))

    def _check_carrier_quotation(self, force_carrier_id=None):
        self.ensure_one()
        DeliveryCarrier = self.env['delivery.carrier']

        if self.only_services:
            self.write({'carrier_id': None})
            self._remove_delivery_line()
            return True
        else:
            self = self.with_company(self.company_id)
            keep_carrier = self.env.context.get('keep_carrier', False)
            # attempt to use partner's preferred carrier
            if not force_carrier_id and self.partner_shipping_id.property_delivery_carrier_id and not keep_carrier:
                force_carrier_id = self.partner_shipping_id.property_delivery_carrier_id.id

            carrier = force_carrier_id and DeliveryCarrier.browse(force_carrier_id) or self.carrier_id
            available_carriers = self._get_delivery_methods()
            if carrier:
                if carrier not in available_carriers:
                    carrier = DeliveryCarrier
                else:
                    # set the forced carrier at the beginning of the list to be verfied first below
                    available_carriers -= carrier
                    available_carriers = carrier + available_carriers
            if force_carrier_id or not carrier or carrier not in available_carriers:
                for delivery in available_carriers:
                    verified_carrier = delivery._match_address(self.partner_shipping_id)
                    if verified_carrier:
                        carrier = delivery
                        break
                self.write({'carrier_id': carrier.id})
            self._remove_delivery_line()
            if carrier:
                # res = carrier.rate_shipment(self)
                res = get_shipment(self)
                print("res")
                print(res)
                rate = {}
                # print("carrier_id")
                # print(carrier.id)
                # print("bgrate")
                # print(bgrate)
                for i in res:
                    # print("for i in bgrate sale")
                    # print(i)
                    # print(carrier.id)
                    if int(i) == carrier.id:
                        # print("si")
                        # print(res[i])
                        rate['success'] = True
                        rate['price'] = res[i]
                        rate['error_message'] = False
                        rate['warning_message'] = False
                        rate['carrier_price'] = res[i]
                    # else:
                    #     rate['success'] = False
                    #     rate['price'] = 0.0
                    #     rate['error_message'] = "Sorry, no shipment to this country. Please contact us for an solution."
                    #     rate['warning_message'] = False
                    #     rate['carrier_price'] = 0.0
                # print("rate")
                # print(rate)
                if rate.get('success'):
                    self.set_delivery_line(carrier, rate['price'])
                    self.delivery_rating_success = True
                    self.delivery_message = rate['warning_message']
                else:
                    self.set_delivery_line(carrier, 0.0)
                    self.delivery_rating_success = False
                    self.delivery_message = "Sorry, no shipment to this country. Please contact us for an solution."

        return bool(carrier)

    def _get_delivery_methods(self):
        address = self.partner_shipping_id
        # searching on website_published will also search for available website (_search method on computed field)
        return self.env['delivery.carrier'].sudo().search([('website_published', '=', True)]).available_carriers(address)

    def _cart_update(self, product_id=None, line_id=None, add_qty=0, set_qty=0, **kwargs):
        """ Override to update carrier quotation if quantity changed """

        self._remove_delivery_line()

        # When you update a cart, it is not enouf to remove the "delivery cost" line
        # The carrier might also be invalid, eg: if you bought things that are too heavy
        # -> this may cause a bug if you go to the checkout screen, choose a carrier,
        #    then update your cart (the cart becomes uneditable)
        self.write({'carrier_id': False})

        values = super(SaleOrder, self)._cart_update(product_id, line_id, add_qty, set_qty, **kwargs)

        return values
