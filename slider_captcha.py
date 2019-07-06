# coding:utf-8
__author__ = 'xxj'

from PIL import Image
import time
from numpy import array
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import WebDriverException
import requests, io, re
# import easing
import lxml.etree


def convert_css_to_offset(px):
    ps = px.replace('px', '').split(' ')
    x = -int(ps[0])
    y = -int(ps[1])
    return x, y, x + 10, y + 58


def convert_index_to_offset(index):
    row = int(index / 26)
    col = index % 26
    x = col * 10
    y = row * 58
    return x, y, x + 10, y + 58


def get_slider_offset_from_diff_image(im_obj):    # diff是滑块图片对象
    '''
    获取图片的偏移量()
    :param diff: 图片对象
    :return:滑块图片的偏移量
    '''
    im = array(im_obj)
    # print im
    width, height = im_obj.size
    # print '宽和高：', width, height
    slider_offset_ls = []
    for i in range(height):    # 高
        for j in range(width):    # 宽
            # black is not only (0,0,0)
            # print 'i;j：', i, j
            # print 'im[i, j, 0]：', im[i, j, 0]    # r
            # print 'im[i, j, 1]：', im[i, j, 1]    # g
            # print 'im[i, j, 2]：', im[i, j, 2]    # b
            if im[i, j, 0] > 15 or im[i, j, 1] > 15 or im[i, j, 2] > 15:
                slider_offset_ls.append(j)
                break
    # print 'slider_offset_ls列表的值：', slider_offset_ls
    slider_offset = min(slider_offset_ls)
    # print '滑块的偏移量：', slider_offset
    return slider_offset


def is_similar(image1, image2, x, y):
    '''
    对比RGB值
    '''
    pass

    pixel1 = image1.getpixel((x, y))
    pixel2 = image2.getpixel((x, y))

    for i in range(0, 3):
        if abs(pixel1[i] - pixel2[i]) >= 50:
            return False

    return True


def get_diff_location(image1, image2):
    '''
    计算缺口的位置
    '''
    for i in range(0, 260):     # 宽
        for j in range(0, 116):    # 高
            if is_similar(image1, image2, i, j) == False:
                return i


def get_slider_offset(image_url, image_url_bg, css):
    '''
    获取背景图片中滑块凹槽的偏移量
    :param image_url: 完整背景图片url（切割）
    :param image_url_bg: 有凹槽的背景图片url（切割）
    :param css: 每张完整的背景图片的position的值
    :return:
    '''
    image_file = io.BytesIO(requests.get(image_url).content)
    im = Image.open(image_file)     # 完整的背景图片对象
    image_file_bg = io.BytesIO(requests.get(image_url_bg).content)
    im_bg = Image.open(image_file_bg)       # 有缺陷的背景图片对象

    # 10*58 26/row => background image size = 260*116
    captcha = Image.new('RGB', (260, 116))    # 按照图片大小初始化一个大小一样的新图片对象
    captcha_bg = Image.new('RGB', (260, 116))
    for i, px in enumerate(css):    # 遍历position值（根据position的值，将乱序的背景图片合成为一份完整的背景图片）
        offset = convert_css_to_offset(px)
        region = im.crop(offset)
        region_bg = im_bg.crop(offset)
        offset = convert_index_to_offset(i)
        captcha.paste(region, offset)    # 合成一张完整的背景图片
        captcha_bg.paste(region_bg, offset)    # 合成一张有凹槽的背景图片

    # captcha.save(r'F:\ENVS\py2\HUAKAI_CAPTCHA\slice\captcha.png')
    # captcha_bg.save(r'F:\ENVS\py2\HUAKAI_CAPTCHA\slice\captcha_bg.png')

    bg_offset = get_diff_location(captcha, captcha_bg)    # 背景图片的缺陷位置的偏移量接口
    # print '背景图片中缺陷位置的偏移量：', bg_offset
    return bg_offset


def get_image_css(images):
    css = []
    for image in images:
        style_position = image.get_attribute("style")    # 参数是每张图片的属性
        match = re.match('background-image: url\("(.*?)"\); background-position: (.*?);', style_position)  # background-position: -205px 0px;
        position = match.group(2)  # 获取position的值
        # print position
        css.append(position)
    return css


def get_track(distance):
    """
    根据偏移量获取移动轨迹（主要是用来滑块的滑动轨迹）
    :param distance: 偏移量
    :return: 移动轨迹
    """
    # 移动轨迹列表
    track = []
    # 滑块的移动量
    currents = []
    # 当前位移
    current = 0
    # 减速阈值
    mid = distance * 4 / 5
    # 计算间隔
    t = 0.15
    # 初速度
    v = 0

    while current < distance:
        if current < mid:
            # 加速度为正2
            a = 2
        else:
            # 加速度为负3
            a = -3
        # 初速度v0
        v0 = v
        # 当前速度v = v0 + at
        v = v0 + a * t
        # 移动距离x = v0t + 1/2 * a * t^2
        move = v0 * t + 1 / 2 * a * t * t
        # 当前位移
        current += move
        # 滑块的移动量
        currents.append(current)
        # 加入轨迹
        track.append(round(move))
    return track, currents


def move_to_gap(browser, knob, track):
    """
    拖动滑块到缺口处
    :param slider: 滑块
    :param track: 轨迹
    :return:
    """
    ActionChains(browser).click_and_hold(knob).perform()
    for x in track:
        ActionChains(browser).move_by_offset(xoffset=x, yoffset=0).perform()
    time.sleep(0.5)
    ActionChains(browser).release().perform()


def fake_drag(browser, knob, offset):
    '''
    模拟人性的滑动行为（防止被识别为机器行为）
    :param browser: 游览器对象
    :param knob: 移动滑块对象
    :param offset: 移动滑块移动的距离
    :return:
    '''
    offsets, tracks = easing.get_tracks(offset, 10, 'ease_out_expo')
    print 'offsets：', offsets, len(offsets)
    print 'tracks：', tracks, len(tracks)
    ActionChains(browser).click_and_hold(knob).perform()
    for x in tracks:
        ActionChains(browser).move_by_offset(x, 0).perform()
    ActionChains(browser).release().perform()


def slider_picture(browser):
    '''
    获取滑块图片的偏移量
    :param browser:
    :return:
    '''
    slice = browser.find_element_by_class_name("gt_slice")
    style = slice.get_attribute("style")
    match = re.search('background-image: url\("(.*?)"\);', style)
    url = match.group(1)
    # print '滑块图片url：', url
    image_file = io.BytesIO(requests.get(url).content)
    im = Image.open(image_file)
    # im.save(r'F:\ENVS\py2\HUAKAI_CAPTCHA\slice\slice.png')  # 获取图片并保存
    slider_offset = get_slider_offset_from_diff_image(im)    # 滑块的偏移量
    return slider_offset


def slider_captcha(wait, browser, thread_name):
    '''
    滑块验证码
    :param browser: 游览器对象
    :return:
    '''
    try:
        wait.until(EC.presence_of_element_located((By.XPATH, '//div[@id="geetest_float_captcha"]')),
                   message='geetest_float_captcha ele not exist')
        slice_offset = slider_picture(browser)    # 获取滑块图片偏移量接口

        images = browser.find_elements_by_class_name("gt_cut_fullbg_slice")
        image_style = images[0].get_attribute("style")
        match = re.match('background-image: url\("(.*?)"\); background-position: (.*?);', image_style)
        image_url = match.group(1)
        css = get_image_css(images)

        images_bg = browser.find_elements_by_class_name("gt_cut_bg_slice")
        image_bg_style = images_bg[0].get_attribute("style")
        match = re.match('background-image: url\("(.*?)"\); background-position: (.*?);', image_bg_style)
        image_bg_url = match.group(1)

        offset = get_slider_offset(image_url, image_bg_url, css)    # 背景图片缺陷位置偏移量接口

        knob = browser.find_element_by_class_name("gt_slider_knob")  # 滑动按钮
        # fake_drag(browser, knob, offset - slice_offset)    # 通过获取滑块图片的偏移量和背景图片中凹槽的偏移量；然后进行滑块的滑动
        track, currents = get_track(offset - slice_offset)  # 获取滑动轨迹
        # print '滑动轨迹：', track
        # print '滑动轨迹长度：', sum(track)
        # print '滑块移动总长度：', currents
        move_to_gap(browser, knob, track)  # 滑块

        # 极验滑块验证码接口
        # time.sleep(2)
        # submit = wait.until(
        #     EC.element_to_be_clickable((By.XPATH, '//input[@id="embed-submit"]'))
        # )
        # submit.click()  # 点击登录
        # wait.until_not(EC.presence_of_element_located((By.XPATH, '//input[@id="embed-submit"]')),
        #                message='slider captcha failed, retry again')

        # 检验滑块验证码是否滑动成功
        wait.until(EC.presence_of_element_located((By.XPATH, '//div/h3')),
                   message='ip_address failed, retry again....')
        content = browser.page_source
        response_xpath = lxml.etree.HTML(content)
        ip_address = response_xpath.xpath('//div/h3/text()')  # IP地址
        if ip_address:
            if '您查询的IP:' in ip_address[0]:
                print '{t} 验证码成功 thread_name：{thread_name}'.format(t=time.strftime('[%Y-%m-%d %H:%M:%S]'),
                                                                         thread_name=thread_name)
            # else情况就是针对验证成功，但是没有ip地址标签（出现再分析）

        # wait.until(EC.presence_of_element_located((By.XPATH, '//div[@id="showDIV"]')),
        #            message='ip_map failed, retry again....')    # 有的没有该标签， 但是也是验证成功的案例

    except WebDriverException as e:    # 刷新验证码
        if 'ip_address failed' in str(e):
            print '{t} slider中WebDriverException异常信息：{message} thread_name：{thread_name}'.format(
                        t=time.strftime('[%Y-%m-%d %H:%M:%S]'), message=str(e).strip(), thread_name=thread_name)
            browser.refresh()
            print '页面刷新...'
            # time.sleep(2)
            return slider_captcha(wait, browser, thread_name)
        else:
            print '{t} slider中WebDriverException异常信息：{message} thread_name：{thread_name}'.format(
                t=time.strftime('[%Y-%m-%d %H:%M:%S]'), message=str(e).strip(), thread_name=thread_name)
            return 'baseexception'

    except BaseException as e:
        print '{t} slider中BaseException异常信息：{message} thread_name：{thread_name}'.format(
                    t=time.strftime('[%Y-%m-%d %H:%M:%S]'), message=str(e).strip(), thread_name=thread_name)
        return 'baseexception'


def main():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--start-maximized")
    browser = webdriver.Chrome(
        executable_path=r'C:\Users\xj.xu\Downloads\chromedriver_win32\chromedriver.exe',
        chrome_options=chrome_options)
    wait = WebDriverWait(browser, 20)

    browser.get('https://www.tianyancha.com/login')
    time.sleep(2)
    login_button = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@class="title-tab text-center"]/div[@class="title"]')),
                              message='password login ele not exist')
    login_button.click()
    # login_button.send_keys(Keys.ENTER)
    print '点击密码登录栏'
    time.sleep(2)
    tel = wait.until(
        EC.presence_of_element_located((By.XPATH, '//div[@class="modulein modulein1 mobile_box  f-base collapse in"]//div[@class="pb30 position-rel"]/input[@class="input contactphone"]'))
    )
    tel.send_keys('18668045631')
    password = wait.until(
        EC.presence_of_element_located((By.XPATH, '//div[@class="modulein modulein1 mobile_box  f-base collapse in"]//div[@class="input-warp -block"]/input[@class="input contactword input-pwd"]'))
    )
    password.send_keys('abcd1234')
    submit = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//div[@class="modulein modulein1 mobile_box  f-base collapse in"]/div[@class="btn -hg btn-primary -block"]'))
    )
    submit.click()    # 点击登录
    time.sleep(10)

    # 出现滑块验证码后的处理方法：do_crack()

    slider_captcha(wait, browser)    # do_crack()接口   处理滑块验证码接口

    time.sleep(10)


if __name__ == '__main__':
    main()
