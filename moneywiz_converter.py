#! /usr/bin/env python
# coding: UTF-8

import json
import argparse
import csv
import datetime
import os
import io
import sys
from os import path
import locale


EXPENSES_TMPLATE = """ * %s
    %s                 -%s %s
    Expenses:%s                 +%s %s
"""

EXPENSES_REFUND_TMPLATE = """ * %s
    %s                 +%s %s
    Expenses:%s                 -%s %s
"""

COMMON_TEMPLATE = """ * %s
    %s                 +%s %s
    %s                 -%s %s
"""



def load_json(filename):
    fd = open(filename, 'r', encoding="UTF-8")
    data = fd.read()
    js = json.loads(data)
    fd.close()
    return js

def load_csv(filename, is_strip_head=False):
    fd = open(filename, 'r', encoding="UTF-8")
    csv_reader = csv.reader(fd, delimiter=',')
    records = []
    for row in csv_reader:
        records.append(tuple(row))
    return records[1:] if is_strip_head else records


def build_records(mapping, record):
    def description_and_tags(desc, tags):
        if tags:
            tags = tags.split(";")
            beancount_tag = ""
            for tag in tags:
                if tag.strip():
                    beancount_tag += "#" + mapping['tags'][tag.strip()] + " "
            return '"%s" %s' % (desc, beancount_tag)
        else:
            return '"%s"' % desc

    name, _, account, transfers_to, description, _, category, date, _, amount, currency, _, _ = record
    if name:
        # This record only contains the current balance in this account
        pass
    else:
        time = datetime.datetime.strptime(date, "%Y/%m/%d")
        # time = time.strftime('%Y-%m-%d')
        amount = locale.atof(amount)
        if transfers_to:
            # This is a transfer between accounts record
            if amount > 0:
                # dedup the same transfer in different accounts
                return (time, COMMON_TEMPLATE % (description_and_tags(description, None), mapping['accounts'][account],
                    amount, currency, mapping['accounts'][transfers_to], amount, currency))
        else:
            if amount > 0 and "退" not in description:
                # Income, refund is added to expenses
                if category:
                    return (time, COMMON_TEMPLATE % (description_and_tags(description, None), mapping['accounts'][account],
                        amount, currency, mapping['incomes'][category], amount, currency))
                else:
                    return (time, COMMON_TEMPLATE % (description_and_tags(description, None), mapping['accounts'][account],
                        amount, currency, "Income:Error", amount, currency))
            else:
                if amount < 0:
                    amount = abs(amount)
                    if category:
                        if "押金" in category:
                            return (time, COMMON_TEMPLATE % (description_and_tags(description, None), "Assets:Receivables:RentalDeposit", amount, currency, mapping['accounts'][account],
                            amount, currency))
                        cate = mapping['expenses'][category]
                        if "其他" in category:
                            if "快递" in description:
                                cate = "Comm:Express"
                            elif "捐赠" in description or "筹" in description:
                                cate = "Social:Donation"
                            elif "红包" in description:
                                cate = "Social:RedEnvelope"
                            elif "互" in description:
                                cate = "Insurance:Health"
                            elif "信用卡保险" in description:
                                cate = "Insurance:CreditCard"
                            elif "手续" in description:
                                cate = "Interest"
                            else:
                                cate = "Shopping:Groceries"
                        elif "交通" in category:
                            if "滴滴" in description or "出租车" in description:
                                cate = "Transport:Taxi"
                            elif "火车" in description:
                                cate = "Transport:Train"
                            elif "机票" in description:
                                cate = "Transport:Aviation"
                            elif "船" in description:
                                cate = "Transport:Ferry"
                            else:
                                cate = "Transport:Public"
                        return (time, EXPENSES_TMPLATE % (description_and_tags(description, None), mapping['accounts'][account],
                            amount, currency, cate, amount, currency))
                    else:
                        # for new balance
                        return (time, COMMON_TEMPLATE % (description_and_tags(description, None), "Expenses:Error", amount, currency, mapping['accounts'][account],
                            amount, currency))
                else:
                    # refund
                    if "押金" in category:
                        return (time, COMMON_TEMPLATE % (description_and_tags(description, None), mapping['accounts'][account],
                                amount, currency, mapping["assets"]["房屋>押金"], amount, currency))

                    cata = "Shopping:Groceries" if "其他" in category else mapping['expenses'][category]
                    return (time, EXPENSES_REFUND_TMPLATE % (description_and_tags(description, None), mapping['accounts'][account],
                            amount, currency, cata, amount, currency))

def print_records(mapping, records):
    print('; transactions generated by moneywiz export CSV file via converting script https://github.com/ziyi-yan/beancount_importer/blob/master/moneywiz_converter.py')
    for record in records:
        beancount_record = build_records(mapping, record)
        if beancount_record:
            print(build_records(mapping, record))

def convert_records(mapping, records):
    result = []
    for record in records:
        beancount_record = build_records(mapping, record)
        if beancount_record:
            result.append(beancount_record)
    return result

import sys

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

    mapping = load_json(path.join(os.path.dirname(os.path.realpath(__file__)), 'map.json'))
    moneywiz_csv_path = sys.argv[1]
    records = load_csv(moneywiz_csv_path, True)
    result = convert_records(mapping, records)
    result.sort(key=lambda r: r[0])
    split = [0]
    f = open("ledger/" + str(result[0][0].year) + "-" + str(result[0][0].month) + ".bean", "w", encoding="utf-8")
    for index, item in enumerate(result):
        if result[split[-1]][0].month != item[0].month:
            split.append(index)
            f.close()
            f = open("ledger/" + str(result[split[-1]][0].year) + "-" + str(result[split[-1]][0].month) + ".bean", "w", encoding="utf-8")
        f.write(item[0].strftime('%Y-%m-%d') + item[1])
    f.close()