# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

import requests
from requests.structures import CaseInsensitiveDict
from odoo.addons.website_sale_delivery.controllers.bggat import GAT
from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.exceptions import UserError


with open("/PATH/addons/website_sale_delivery/controllers/.access_token") as f:
    access_token = f.read()

base_url = "https://api.banggood.com"
params = {"lang": "en", "access_token": access_token}


def make_get_request(url: str, params: dict) -> object:

    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"
    headers["Connection"] = "close"

    # params["access_token"] = GAT.get_access_token()
    response = requests.get(url=url, params=params, headers=headers)
    response = json.loads(response.text)

    if response["code"] == 21020 or response["code"] == 21030 or response["code"] == 11020:

        # print(response)
        params["access_token"] = GAT.get_access_token()
        response = requests.get(url=url, params=params, headers=headers)
        response = json.loads(response.text)

        return response

    elif response["code"] == 31020:

        print("make_get_request(MAIN) " + str(response), file=open('PATH', 'a'))
        return 0

    return response


def get_shipment(order):
    # order = request.website.sale_get_order()
    # print(len(order.order_line))

    # params = {"lang": "en"}
    # params["access_token"] = access_token
    url = base_url + "/product/getShipments"

    shipment = {"4": "Sorry, no shipment to this country. Please contact us for an solution.",
                "5": "Sorry, no shipment to this country. Please contact us for an solution."}

    # country
    # print(order.partner_shipping_id.country_code)
    for line in order.order_line:
        print("line.product.attribute")
        # print(order.order_line)
        if line.product_id.default_code:
            # # quantity
            # print("request00")
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

            response = make_get_request(url=url, params=params)
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
                print("get_shipment(MAIN) " + str(response), file=open('PATH', 'a'))
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


class WebsiteSaleDelivery(WebsiteSale):

    @http.route()
    def shop_payment(self, **post):
        order = request.website.sale_get_order()
        carrier_id = post.get('carrier_id')
        keep_carrier = post.get('keep_carrier', False)
        if keep_carrier:
            keep_carrier = bool(int(keep_carrier))
        if carrier_id:
            carrier_id = int(carrier_id)
        if order:
            order.with_context(keep_carrier=keep_carrier)._check_carrier_quotation(force_carrier_id=carrier_id)
            if carrier_id:
                return request.redirect("/shop/payment")

        return super(WebsiteSaleDelivery, self).shop_payment(**post)

    @http.route(['/shop/update_carrier'], type='json', auth='public', methods=['POST'], website=True, csrf=False)
    def update_eshop_carrier(self, **post):
        order = request.website.sale_get_order()
        carrier_id = int(post['carrier_id'])
        if order and carrier_id != order.carrier_id.id:
            if any(tx.state not in ("canceled", "error", "draft") for tx in order.transaction_ids):
                raise UserError(_('It seems that there is already a transaction for your order, you can not change the delivery method anymore'))
            order._check_carrier_quotation(force_carrier_id=carrier_id)
        return self._update_website_sale_delivery_return(order, **post)

    @http.route(['/shop/carrier_rate_shipment'], type='json', auth='public', methods=['POST'], website=True)
    def cart_carrier_rate_shipment(self, carrier_id, **kw):
        order = request.website.sale_get_order(force_create=True)

        if not int(carrier_id) in order._get_delivery_methods().ids:
            raise UserError(_('It seems that a delivery method is not compatible with your address. Please refresh the page and try again.'))

        Monetary = request.env['ir.qweb.field.monetary']

        res = {'carrier_id': carrier_id}
        carrier = request.env['delivery.carrier'].sudo().browse(int(carrier_id))
        # rate = carrier.rate_shipment(order)
        # {'success': False, 'price': 0.0, 'error_message': 'No price rule matching this order; delivery cost cannot be computed.', 'warning_message': False, 'carrier_price': 0.0}
        # {'success': True, 'price': 20.0, 'error_message': False, 'warning_message': False, 'carrier_price': 20.0}
        bgrate = get_shipment(order)
        rate = {}
        # print("carrier_id")
        # print(carrier)
        print("bgrate")
        print(bgrate)
        for i in bgrate:
            # print("for i in bgrate main")
            # print(i)
            # print(carrier_id)
            if i == carrier_id:
                # print("si")
                # print(bgrate[i])
                rate['success'] = True
                rate['price'] = bgrate[i]
                rate['error_message'] = False
                rate['warning_message'] = False
                rate['carrier_price'] = bgrate[i]
        # print("rate")
        # print(rate)
        if rate.get('success'):
            tax_ids = carrier.product_id.taxes_id.filtered(lambda t: t.company_id == order.company_id)
            if tax_ids:
                fpos = order.fiscal_position_id
                tax_ids = fpos.map_tax(tax_ids)
                taxes = tax_ids.compute_all(
                    rate['price'],
                    currency=order.currency_id,
                    quantity=1.0,
                    product=carrier.product_id,
                    partner=order.partner_shipping_id,
                )
                if request.env.user.has_group('account.group_show_line_subtotals_tax_excluded'):
                    rate['price'] = taxes['total_excluded']
                else:
                    rate['price'] = taxes['total_included']

            res['status'] = True
            res['new_amount_delivery'] = Monetary.value_to_html(rate['price'], {'display_currency': order.currency_id})
            res['is_free_delivery'] = not bool(rate['price'])
            res['error_message'] = rate['warning_message']
        else:
            res['status'] = False
            res['new_amount_delivery'] = Monetary.value_to_html(0.0, {'display_currency': order.currency_id})
            res['error_message'] = "Sorry, no shipment to this country. Please contact us for an solution."
        return res

    def order_lines_2_google_api(self, order_lines):
        """ Transforms a list of order lines into a dict for google analytics """
        order_lines_not_delivery = order_lines.filtered(lambda line: not line.is_delivery)
        return super(WebsiteSaleDelivery, self).order_lines_2_google_api(order_lines_not_delivery)

    def order_2_return_dict(self, order):
        """ Returns the tracking_cart dict of the order for Google analytics """
        ret = super(WebsiteSaleDelivery, self).order_2_return_dict(order)
        delivery_line = order.order_line.filtered('is_delivery')
        if delivery_line:
            ret['shipping'] = delivery_line.price_unit
        return ret

    def _get_shop_payment_values(self, order, **kwargs):
        values = super(WebsiteSaleDelivery, self)._get_shop_payment_values(order, **kwargs)
        has_storable_products = any(line.product_id.type in ['consu', 'product'] for line in order.order_line)

        if not order._get_delivery_methods() and has_storable_products:
            values['errors'].append(
                (_('Sorry, we are unable to ship your order'),
                 _('No shipping method is available for your current order and shipping address. '
                   'Please contact us for more information.')))

        if has_storable_products:
            if order.carrier_id and not order.delivery_rating_success:
                order._remove_delivery_line()

            delivery_carriers = order._get_delivery_methods()
            values['deliveries'] = delivery_carriers.sudo()

        values['delivery_has_storable'] = has_storable_products
        values['delivery_action_id'] = request.env.ref('delivery.action_delivery_carrier_form').id
        return values

    def _update_website_sale_delivery_return(self, order, **post):
        Monetary = request.env['ir.qweb.field.monetary']
        carrier_id = int(post['carrier_id'])
        currency = order.currency_id
        if order:
            return {
                'status': order.delivery_rating_success,
                'error_message': order.delivery_message,
                'carrier_id': carrier_id,
                'is_free_delivery': not bool(order.amount_delivery),
                'new_amount_delivery': Monetary.value_to_html(order.amount_delivery, {'display_currency': currency}),
                'new_amount_untaxed': Monetary.value_to_html(order.amount_untaxed, {'display_currency': currency}),
                'new_amount_tax': Monetary.value_to_html(order.amount_tax, {'display_currency': currency}),
                'new_amount_total': Monetary.value_to_html(order.amount_total, {'display_currency': currency}),
                'new_amount_total_raw': order.amount_total,
            }
        return {}
