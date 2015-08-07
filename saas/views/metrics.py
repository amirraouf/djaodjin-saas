# Copyright (c) 2015, DjaoDjin inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import json
from datetime import datetime

from django.core.urlresolvers import reverse
from django.views.generic import ListView, TemplateView

from saas.api.coupons import SmartCouponListMixin
# NB: there is another CouponMixin
from saas.api.coupons import CouponMixin as CouponAPIMixin
from saas.api.metrics import RegisteredQuerysetMixin
from saas.managers.metrics import monthly_balances, month_periods
from saas.mixins import (CouponMixin, OrganizationMixin, MetricsMixin,
    ChurnedQuerysetMixin, SubscriptionSmartListMixin, SubscribedQuerysetMixin,
    UserSmartListMixin)
from saas.models import CartItem, Plan, Transaction
from saas.views.download import CSVDownloadView
from saas.utils import datetime_or_now


class CouponMetricsView(CouponMixin, ListView):
    """
    Performance of Coupon based on CartItem.

    Template:

    To edit the layout of this page, create a local \
    ``saas/metrics/coupons.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/metrics/coupons.html>`__).

    Template context:
      - organization
      - request
    """

    model = CartItem
    paginate_by = 10
    template_name = 'saas/metrics/coupons.html'

    def get_queryset(self):
        queryset = super(CouponMetricsView, self).get_queryset().filter(
            coupon=self.get_coupon(), recorded=True)
        return queryset

    def get_context_data(self, **kwargs):
        context = super(CouponMetricsView, self).get_context_data(**kwargs)
        context.update({'coupon_performance_count': CartItem.objects.filter(
            coupon=self.get_coupon(), recorded=True).count()})
        return context


class CouponMetricsDownloadView(SmartCouponListMixin, CouponAPIMixin,
                                OrganizationMixin, CSVDownloadView):

    headings = [
        'Code',
        'Percentage',
        'Name',
        'Email',
        'Plan',
    ]

    def get_headings(self):
        return self.headings

    def get_filename(self):
        return datetime.now().strftime('coupons-%Y%m%d.csv')

    def get_queryset(self):
        '''
        Return CartItems related to the Coupon specified in the URL.
        '''
        # invoke SmartCouponListMixin to get the coupon specified by URL params
        coupons = super(CouponMetricsDownloadView, self).get_queryset()
        # get related CartItems
        return CartItem.objects.filter(coupon__in=coupons)

    def queryrow_to_columns(self, cartitem):
        return [
            cartitem.coupon.code.encode('utf-8'),
            cartitem.coupon.percent,
            ' '.join([cartitem.user.first_name, cartitem.user.last_name]).\
                encode('utf-8'),
            cartitem.user.email.encode('utf-8'),
            cartitem.plan.slug.encode('utf-8'),
        ]


class PlansMetricsView(OrganizationMixin, TemplateView):
    """
    Performance of Plans for a time period
    (as a count of subscribers per plan per month)

    Template:

    To edit the layout of this page, create a local \
    ``saas/metrics/plans.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/metrics/plans.html>`__).
    The page will typically call back
    :ref:`/api/metrics/:organization/plans/ <api_metrics_plans>`
    to fetch the 12 month trailing performance in terms of subscribers
    of the plans of a provider.

    Template context:
      - organization
      - request
    """

    template_name = 'saas/metrics/plans.html'

    def get_context_data(self, **kwargs):
        context = super(PlansMetricsView, self).get_context_data(**kwargs)
        tables = [
            {"title": "Active subscribers",
            "key": "plan",
            "active": True,
            "location": reverse('saas_api_plan',
                            args=(self.get_organization(),))},
        ]
        context.update({
            "title": "Plans",
            "tables" : json.dumps(tables),
        })

        plans = Plan.objects.filter(organization=self.get_organization())
        context.update({"plans": plans})
        return context


class RevenueMetricsView(MetricsMixin, TemplateView):
    """
    Reports cash flow and revenue in currency units.

    Template:

    To edit the layout of this page, create a local \
    ``saas/metrics/base.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/metrics/base.html>`__).

    The page will typically call back
    :ref:`/api/metrics/:organization/funds/ <api_metrics_funds>`
    to fetch the 12 month trailing cash flow table, and/or
    :ref:`/api/metrics/:organization/balances/ <api_metrics_balances>`
    to fetch the 12 month trailing receivable/backlog/income revenue.

    The example page also calls back
    :ref:`/api/metrics/:organization/customers/ <api_metrics_customers>`
    to fetch the distinct number of customers that generated the cash
    transactions.

    Template context:
      - organization
      - request
    """

    template_name = 'saas/metrics/base.html'

    def get_context_data(self, **kwargs):
        context = super(RevenueMetricsView, self).get_context_data(**kwargs)
        context.update({
            "title": "Revenue",
            "tables": [{"key": "cash",
                        "title": "Cash flow",
                        "unit": "$",
                        "location": reverse('saas_api_revenue',
                            args=(self.organization,))},
                       {"key": "balances",
                        "title": "Balances",
                        "unit": "$",
                        "location": reverse('saas_api_balances',
                            args=(self.organization,))},
                       {"key": "customer",
                        "title": "Customers",
                        "location": reverse('saas_api_customer',
                            args=(self.organization,))}]})
        return context


class BalancesDownloadView(MetricsMixin, CSVDownloadView):
    """
    Export balance metrics as a CSV file.
    """
    queryname = 'balances'

    def get_headings(self):
        return ['name'] + [
            end_period for end_period in month_periods(from_date=self.ends_at)]

    def get_filename(self, *_):
        return '{}.csv'.format(self.queryname)

    def get(self, request, *args, **kwargs): #pylint: disable=unused-argument
        # cache_fields sets attributes like 'starts_at',
        # required by other methods
        self.cache_fields(request)
        return super(BalancesDownloadView, self).get(request, *args, **kwargs)

    def get_queryset(self, *_):
        return Transaction.objects.distinct_accounts()

    def queryrow_to_columns(self, account):
        return [account] + [item[1] for item in monthly_balances(
            self.organization, account, self.ends_at.date())]


class RegisteredBaseDownloadView(RegisteredQuerysetMixin, CSVDownloadView):

    def get_headings(self):
        return ['First name', 'Last name', 'Email', 'Registration Date']

    def get_filename(self):
        return 'registered-{}.csv'.format(datetime_or_now().strftime('%Y%m%d'))

    def queryrow_to_columns(self, instance):
        return [
            instance.first_name.encode('utf-8'),
            instance.last_name.encode('utf-8'),
            instance.email.encode('utf-8'),
            instance.date_joined.date(),
        ]


class RegisteredDownloadView(UserSmartListMixin, RegisteredBaseDownloadView):

    pass


class SubscriptionBaseDownloadView(CSVDownloadView):

    subscriber_type = None

    def get_queryset(self):
        raise NotImplementedError()

    def get_headings(self):
        return ['Name', 'Email', 'Plan', 'Since', 'Until']

    def get_filename(self):
        return 'subscribers-{}-{}.csv'.format(
            self.subscriber_type, datetime_or_now().strftime('%Y%m%d'))

    def queryrow_to_columns(self, instance):
        return [
            instance.organization.full_name.encode('utf-8'),
            instance.organization.email.encode('utf-8'),
            instance.plan.title.encode('utf-8'),
            instance.created_at.date(),
            instance.ends_at.date(),
        ]


class ActiveSubscriptionBaseDownloadView(SubscribedQuerysetMixin,
                                         SubscriptionBaseDownloadView):

    subscriber_type = 'active'

class ActiveSubscriptionDownloadView(SubscriptionSmartListMixin,
                                     ActiveSubscriptionBaseDownloadView):

    pass


class ChurnedSubscriptionBaseDownloadView(ChurnedQuerysetMixin,
                                         SubscriptionBaseDownloadView):

    subscriber_type = 'churned'


class ChurnedSubscriptionDownloadView(SubscriptionSmartListMixin,
                                      ChurnedSubscriptionBaseDownloadView):

    pass
