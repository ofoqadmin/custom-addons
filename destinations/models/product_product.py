from odoo import api, fields, models, _, tools
import math
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError

class ProductProduct(models.Model):
    _inherit = 'product.product'
                
     
    @api.constrains('dest_id','dest_product_code')
    def _check_duplicate_dest(self):
        for record in self:
            prodids = self.search([('dest_id', '=', record.dest_id.id),('dest_product_code','=',self.dest_product_code), ('id', '!=', record.id)])
            if len(prodids) >= 1:
                raise ValidationError("Product Code must be unique within each Entity")
                

    def _get_best_dest_pricing_rule(self, **kwargs):
        """Return the best pricing rule for the given duration.

        :param float duration: duration, in unit uom
        :param str unit: duration unit (hour, day, week)
        :param datetime start_date:
        :param datetime end_date:
        :return: least expensive pricing rule for given duration
        :rtype: destination.product.variabledaily.lines
        """
        self.ensure_one()
        best_pricing_rule = self.env['destination.product.variabledaily.lines']
        if not self.dest_rental_pricing_ids:
            return best_pricing_rule
        start_date, end_date = kwargs.get('start_date', False), kwargs.get('end_date', False)
        duration, unit = kwargs.get('duration', False), kwargs.get('unit', '')
        pricelist = kwargs.get('pricelist', self.env['product.pricelist'])
        currency = kwargs.get('currency', self.env.company.currency_id)
        company = kwargs.get('company', self.env.company)
        if start_date and end_date:
            duration_dict = self.env['destination.product.variabledaily.lines']._compute_duration_vals(start_date, end_date)
        elif not(duration and unit):
            return best_pricing_rule  # no valid input to compute duration.
        min_price = float("inf")  # positive infinity
        available_pricings = self.dest_rental_pricing_ids.filtered(
            lambda p: p.pricelist_id == pricelist
        )
        if not available_pricings:
            # If no pricing is defined for given pricelist:
            # fallback on generic pricings
            available_pricings = self.dest_rental_pricing_ids.filtered(
                lambda p: not p.pricelist_id
            )
        for pricing in available_pricings:
            if pricing.applies_to(self):
                if duration and unit:
                    price = pricing._compute_price(duration, unit)
                else:
                    price = pricing._compute_price(duration_dict[pricing.unit], pricing.unit)

                if pricing.currency_id != currency:
                    price = pricing.currency_id._convert(
                        from_amount=price,
                        to_currency=currency,
                        company=company,
                        date=date.today(),
                    )

                if price < min_price:
                    min_price, best_pricing_rule = price, pricing
        return best_pricing_rule
    
    def action_view_dest(self):
        self.ensure_one()
        result = {
            "type": "ir.actions.act_window",
            "res_model": "destination.destination",
            "res_id": self.dest_id.id,
            "view_mode": "form",
             }
        return result