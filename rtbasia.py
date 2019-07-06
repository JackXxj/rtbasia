# coding:utf-8
__author__ = 'xxj'

import time
import os
import requests
import Queue
import re
import datetime
import threading
import redis
from threading import Lock
import lxml.etree
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException
from slider_captcha import slider_captcha
from Queue import Empty
import json
import sys

reload(sys)
sys.setdefaultencoding('utf8')
headers = {
    'accept': '*/*',
    'accept-encoding': 'gzip, deflate, sdch',
    'accept-language': 'zh-CN,zh;q=0.8,en;q=0.6,ja;q=0.4',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36'
}
KEYWORD_QUEUE = Queue.Queue()
PROXY_IP_Q = Queue.Queue()
THREAD_DRIVER_MAP = {}    # 线程与driver的对应关系
THREAD_PROXY_MAP = {}    # 线程与代理的对应关系


class IpException(Exception):
    def __init__(self, message):
        super(IpException, self).__init__()
        self.message = message


def get_redis_proxy():
    '''
    从redis相应的key中获取代理ip
    :return:
    '''
    current_day = time.strftime('%d')
    if start_day != current_day:
        print time.strftime('[%Y-%m-%d %H:%M:%S]'), '退出get_redis_proxy()'
        return False
    rs = redis.StrictRedis(host="172.31.10.75", port=9221)
    rtbasia_proxy_length = rs.llen('spider:rtbasia:proxy:kuai')  # rtbasia
    print time.strftime('[%Y-%m-%d %H:%M:%S]'), 'redis中rtbasia的代理ip长度：', rtbasia_proxy_length
    if rtbasia_proxy_length == 0:
        print time.strftime('[%Y-%m-%d %H:%M:%S]'), 'redis中的代理ip数量为0，等待60s'
        time.sleep(60)
        return get_redis_proxy()
    for i in xrange(rtbasia_proxy_length):
        ip = rs.lpop('spider:rtbasia:proxy:kuai')
        # proxies = {
        #     'http': "http://{ip}".format(ip=ip),
        #     # 'https': "http://8c84700fa7d2:kgvavaeile@{ip}".format(ip=ip)
        # }
        PROXY_IP_Q.put(ip)


def get_driver(ip):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    proxy_https_argument = '--proxy-server=http://{ip}'.format(ip=ip)  # http, https (无密码，或白名单ip授权，成功)
    print 'proxy_https_argument：', proxy_https_argument
    chrome_options.add_argument(proxy_https_argument)
    driver = webdriver.Chrome(chrome_options=chrome_options)
    return driver


def selenium_login(lock, fileout, rs):
    while True:
        current_day = time.strftime('%d')
        if start_day != current_day:
            if THREAD_DRIVER_MAP.has_key(thread_name):
                driver = THREAD_DRIVER_MAP.pop(thread_name)
                # driver.close()
                driver.quit()
            print time.strftime('[%Y-%m-%d %H:%M:%S]'), 'selenium_login()退出'
            return False
        try:
            print 'THREAD_DRIVER_MAP：{l}'.format(l=len(THREAD_DRIVER_MAP))
            thread_name = threading.currentThread().name

            if not THREAD_PROXY_MAP.get(thread_name):
                proxy = PROXY_IP_Q.get(False)
                THREAD_PROXY_MAP[thread_name] = proxy
            proxy = THREAD_PROXY_MAP.get(thread_name)

            if not THREAD_DRIVER_MAP.get(thread_name):
                driver = get_driver(proxy)
                THREAD_DRIVER_MAP[thread_name] = driver
            driver = THREAD_DRIVER_MAP.get(thread_name)
            wait = WebDriverWait(driver, 10)

            keyword = rs.lpop('spider:python:ip:rtbasia:keyword')
            url = 'https://ip.rtbasia.com/?ipstr={ipstr}'.format(ipstr=keyword)
            # print time.strftime('[%Y-%m-%d %H:%M:%S]'), 'url：', url, driver, thread_name
            print '{t} url：{url} thread_name：{thread_name} driver：{driver}'.format(
                t=time.strftime('[%Y-%m-%d %H:%M:%S]'), url=url, thread_name=thread_name, driver=driver)
            driver.get(url)

            wait.until(EC.presence_of_element_located((By.XPATH, '//div[@id="geetest_float_captcha"]')),
                       message='geetest_float_captcha ele not exist')
            print time.strftime('[%Y-%m-%d %H:%M:%S]'), '出现滑块验证码，处理验证码...'

            s = slider_captcha(wait, driver, thread_name)  # 滑块验证码处理接口
            if s == 'baseexception':
                raise IpException('slider baseexception')
            content = driver.page_source
            # browser.quit()  # 退出游览器
            response_xpath = lxml.etree.HTML(content)

            net_location = response_xpath.xpath('//div/h5/span/a/text()')
            if net_location:
                net_location = net_location[0]
            else:
                net_location = ''
            # print '网络位置：', net_location

            other = response_xpath.xpath('//div/h5/span')[0].xpath('string(.)').replace('网络位置:', ''). \
                replace(net_location, '').replace('\n', '').replace('\r', '').replace('\t', '').strip()
            # print 'other：', other
            if ('行为位置' in other) and ('运营商' in other):
                position = other.replace('行为位置', '').replace('运营商', '').strip(':')
                position_ls = position.split(':')
                behavior_location = position_ls[0].strip()
                # print '行为位置：', behavior_location
                operator = position_ls[1].strip()
                # print '运营商：', operator
            elif '行为位置' in other:
                behavior_location = other.replace('行为位置:', '').strip('')
                # print '行为位置：', behavior_location
                operator = ''
                # print '运营商：', operator

            elif '运营商' in other:
                behavior_location = ''
                # print '行为位置：', behavior_location
                operator = other.replace('运营商:', '').strip('')
                # print '运营商：', operator

            else:
                behavior_location = ''
                # print '行为位置：', behavior_location
                operator = ''
                # print '运营商：', operator

            center_label = response_xpath.xpath('//center/label/text()')
            if center_label:
                center_label = center_label[0]
            else:
                center_label = ''
            # print 'center_label：', center_label
            ip_address = response_xpath.xpath('//div/h3/text()')  # IP地址
            if ip_address:
                ip_address = ip_address[0].replace('您查询的IP:', '')
            else:
                ip_address = ''
            # print 'ip地址：', ip_address
            itype = response_xpath.xpath('//span[@class="itype"]/text()')  # 带宽类型
            if itype:
                itype = itype[0]
            else:
                itype = ''
            # print 'itype：', itype
            probability = response_xpath.xpath('//div/span[2]/text()')  # 真人概率
            if probability:
                probability = probability[0].replace('真人概率：', '')
            else:
                probability = ''
            print '真人概率：{}'.format(probability)
            ip_s = re.findall(r'wgs84_to_bd09\(new Coordinate(.*?)\);', content, re.S)
            # print ip_s
            r_s = re.findall(r'new BMap.Circle\(.*?,(.*?)\);', content, re.S)
            # print r_s
            locations = []
            for index, ip in enumerate(ip_s):
                ip = list(eval(ip))
                # print 'ip：', ip, type(ip)
                r = eval(r_s[index])
                # print 'r：', r, type(r)
                ip.append(r)
                # print 'ip_new：', ip
                locations.append(ip)

            content_dict = {'ip': keyword, 'net_location': net_location, 'behavior_location': behavior_location,
                            'operator': operator, 'ip_address': ip_address, 'itype': itype, 'probability': probability,
                            'center_label': center_label, 'locations': locations}
            content = json.dumps(content_dict, ensure_ascii=False)
            data_write_file(lock, fileout, content)

        except Empty as e:
            pass

        except WebDriverException as e:
            with lock:
                # print 'WebDriverException异常信息：', e, type(e), 'e.message：', e.message, type(e.message)
                print '{t} rtb中WebDriverException异常信息：{message} thread_name：{thread_name}'.format(
                    t=time.strftime('[%Y-%m-%d %H:%M:%S]'), message=e.message, thread_name=thread_name)
                rs.rpush('spider:python:ip:rtbasia:keyword', keyword)
                # 1、切换代理； 2、切换代理对应的driver
                THREAD_PROXY_MAP.pop(thread_name)
                driver = THREAD_DRIVER_MAP.pop(thread_name)
                # driver.close()
                driver.quit()
                if PROXY_IP_Q.empty():
                    get_redis_proxy()
                    print '获取到新代理队列中代理ip数量：', PROXY_IP_Q.qsize()
                proxy = PROXY_IP_Q.get(False)
                print '新的代理IP：', proxy
                THREAD_PROXY_MAP[thread_name] = proxy

        except IpException as e:
            with lock:
                # print 'IpException异常信息：', e, type(e), 'e.message：', e.message, type(e.message)
                print '{t} rtb中IpException异常信息：{message} thread_name：{thread_name}'.format(
                    t=time.strftime('[%Y-%m-%d %H:%M:%S]'), message=e.message, thread_name=thread_name)
                rs.rpush('spider:python:ip:rtbasia:keyword', keyword)
                # 1、切换代理； 2、切换代理对应的driver
                THREAD_PROXY_MAP.pop(thread_name)
                driver = THREAD_DRIVER_MAP.pop(thread_name)
                # driver.close()
                driver.quit()
                if PROXY_IP_Q.empty():
                    get_redis_proxy()
                    print '获取到新代理队列中代理ip数量：', PROXY_IP_Q.qsize()
                proxy = PROXY_IP_Q.get(False)
                print '新的代理IP：', proxy
                THREAD_PROXY_MAP[thread_name] = proxy

        except BaseException as e:
            with lock:
                print '{t} rtb中BaseException异常信息：{message} thread_name：{thread_name}'.format(
                    t=time.strftime('[%Y-%m-%d %H:%M:%S]'), message=e.message, thread_name=thread_name)
                rs.rpush('spider:python:ip:rtbasia:keyword', keyword)
                # 1、切换代理； 2、切换代理对应的driver
                THREAD_PROXY_MAP.pop(thread_name)
                driver = THREAD_DRIVER_MAP.pop(thread_name)
                # driver.close()
                driver.quit()
                if PROXY_IP_Q.empty():
                    get_redis_proxy()
                    print '获取到新代理队列中代理ip数量：', PROXY_IP_Q.qsize()
                proxy = PROXY_IP_Q.get(False)
                print '新的代理IP：', proxy
                THREAD_PROXY_MAP[thread_name] = proxy


def data_write_file(lock, fileout, content):
    with lock:
        fileout.write(content)
        fileout.write('\n')
        fileout.flush()


def main():
    display = Display(visible=0, size=(1000, 800))
    display.start()
    time.sleep(1)
    lock = Lock()
    file_time = time.strftime('%Y%m%d')

    rs = redis.StrictRedis(host="172.31.10.75", port=9221)
    rtbasia_keyword_length = rs.llen('spider:python:ip:rtbasia:keyword')
    print 'redis中rtbasia_keyword列表长度：', rtbasia_keyword_length

    get_redis_proxy()  # 将redis中的代理ip放入到PROXY_IP_Q队列中
    proxy_count = PROXY_IP_Q.qsize()
    print time.strftime('[%Y-%m-%d %H:%M:%S]'), '代理ip队列中的ip数量：', proxy_count

    dest_path = '/ftp_samba/112/spider/python/ip_rtbasia'  # linux上的文件目录
    if not os.path.exists(dest_path):
        os.makedirs(dest_path)
    dest_file_name = os.path.join(dest_path, 'rtbasia_' + file_time)
    tmp_file_name = os.path.join(dest_path, 'rtbasia_' + file_time + '.tmp')
    fileout = open(tmp_file_name, 'a')

    threads = []
    for i in xrange(10):
        t = threading.Thread(target=selenium_login, args=(lock, fileout, rs))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    try:
        fileout.flush()
        fileout.close()
    except IOError as e:
        time.sleep(1)
        fileout.close()
    os.rename(tmp_file_name, dest_file_name)
    display.stop()


if __name__ == '__main__':
    print time.strftime('[%Y-%m-%d %H:%M:%S]'), 'start'
    start_day = time.strftime('%d')
    main()
    print time.strftime('[%Y-%m-%d %H:%M:%S]'), 'end'



