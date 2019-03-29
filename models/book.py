# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo import tools, _
import urllib.request, json,base64,time
from urllib.error import HTTPError
from datetime import datetime, timedelta
BORROWDAYS = 30
DOUBAN_API = "https://api.douban.com/v2/book/isbn/%s"
BORROWLIMIT = 1
RESUMEDAYS = 15

def get_doban_img_url(vals):
    isbn = vals.get('isbn')
    if isbn and len(isbn)==13:
        douban_url = DOUBAN_API % (isbn,)
        # print(douban_url)
        douban_req = urllib.request.Request(douban_url)
        # douban_req.add_header('Content-Type', 'text/html;charset=UTF-8')
        try:
            douban_resp = urllib.request.urlopen(douban_req).read().decode()
            # print(douban_resp)
            resp = json.loads(douban_resp)
            rt = resp.get('image', None)
            if rt:
                vals.update({'image_url': rt})
                imgres = urllib.request.urlopen(rt)
                vals.update({'image': base64.b64encode(imgres.read())})
        except HTTPError:
            pass

class BookTag(models.Model):
    _name = 'sce_library.book.tag'
    name = fields.Char('Tag Name', required=True)
    color = fields.Integer('Color Index')
    _sql_constraints = [
            ('name_uniq', 'unique (name)', "Tag name already exists!"),
            ]

class BookKind(models.Model):
    _name = 'sce_library.book.kind'
    _order = 'sequence'

    name = fields.Char('Book Kind', required=True)
    sequence = fields.Integer()
    _sql_constraints = [
            ('name_uniq', 'unique (name)', "Kind name already exists!"),
            ]

class BookLocation(models.Model):
    _name = 'sce_library.location'
    _order = 'sequence'

    name = fields.Char()
    manager_ids = fields.Many2many('res.users')
    sequence = fields.Integer()
    # Constaints
    _sql_constraints = [
            ('name_uniq', 'unique (name)', "Location name already exists!"),
            ]

class BookBorrow(models.Model):
    _name = 'sce_library.book.borrow'

    book_id = fields.Many2one('sce_library.book', ondelete='cascade')
    user_id = fields.Many2one('res.users')
    borrow_date = fields.Datetime()
    overtime_date = fields.Datetime()
    return_date = fields.Datetime()
    resume_date = fields.Datetime()   # 没用到

class Book(models.Model):
    _name = 'sce_library.book'
    _inherit='sce_dingtalk.mixin'

    name = fields.Char(string="Book Title", required=True)
    code = fields.Char(string="QRcode", required=True)
    sub_title = fields.Char(string="Sub Title")
    author = fields.Char()
    publisher = fields.Char()
    isbn = fields.Char()
    description = fields.Text()
    location_id = fields.Many2one('sce_library.location', required=True)
    kind_id = fields.Many2one('sce_library.book.kind', required=True)
    tag_ids = fields.Many2many('sce_library.book.tag', string="Tags")
    borrow_ids = fields.One2many('sce_library.book.borrow', 'book_id', copy=False)
    keeper_id = fields.Many2one('res.users')
    borrow_date = fields.Date()
    overtime_date = fields.Date()
    borrow_times = fields.Integer(default=0, read_only=True)
    resume_times = fields.Integer(default=1)
    # 图片
    image = fields.Binary('Image', attachment=True,
            help="This field holds the image of the book.")
    image_url = fields.Char()
    # 发布控制
    state = fields.Selection(selection=[
        ('available','Available'),
        ('borrowed','Borrowed'),
        ('abnormal','Abnormal'),
        ('lost','Lost'),
        ], default='available') # 默认可借阅
    # Constaints
    _sql_constraints = [
        # (约束名， 约束表达式， 错误提示信息)
            ('code_uniq', 'unique (code)', "QRcode number already exists!"),
            ]
    def resume(self, authCode):
        user = self.dingtalk_get_user(authCode)
        if user and self.state == 'borrowed':
            record = self.env['sce_library.book.borrow'].search([
                ('book_id', '=', self.id),
                ('user_id', '=', self.keeper_id.id),
                ('return_date', '=', False)
            ], order='id desc')
            resume_date = datetime.strptime(record.overtime_date,'%Y-%m-%d %H:%M:%S')+timedelta(days=RESUMEDAYS)
            # print(record.overtime_date)
            # resume_date = datetime.strptime(record.overtime_date,'%Y-%m-%d')+timedelta(days=RESUMEDAYS)
            record.sudo().write({
                'overtime_date': fields.Datetime.context_timestamp(self, resume_date)
            })
            self.sudo().write({
                'resume_times':0,
                'overtime_date': fields.Datetime.context_timestamp(self, resume_date)
            })
            keeper = self.sudo().keeper_id.login.split("@")[0]
            # print('续期')
            # print(keeper)
            overtime_date = record.overtime_date[:10]
            title = ("续借成功：")
            markdown = ("## 续借成功：\n- 书名: 《%s》\n- 请于 %s 前至该楼层管理员处归还本书，谢谢！") % (self.name, overtime_date)
            redirect = "eapp://pages/mybook/mybook?query"
            self.dingtalk_send_action_card_message(keeper, title, markdown, redirect)
            result = {'status':'ok','overtime_date':overtime_date, 'resume':self.resume_times}
        else:
            result = {'status':'failed','reason':'No user or wrong state'}
        return result
    # Borrow with Dingtalk authcode
    def borrow(self, authcode):
        user = self.dingtalk_get_user(authcode)  # user = res.users(7,)
        mybooks = self.get_mybooks(user)
        if len(mybooks) >= BORROWLIMIT:
            return 'overlimit'
        elif self.state=='borrowed':
            return 'borrowed'
        elif user and self.state=='available' and len(mybooks)<BORROWLIMIT:
            rt = self.env['sce_library.book.borrow'].sudo().create({
                'book_id': self.id,
                'user_id': user.id,
                'borrow_date': fields.Datetime.context_timestamp(self, datetime.now()),
                'overtime_date': fields.Datetime.context_timestamp(self, datetime.now()+timedelta(days=BORROWDAYS)),
                })
            if rt:
                self.sudo().write({
                    'state': 'borrowed',
                    'keeper_id': user.id,
                    'borrow_date': rt.borrow_date,
                    'overtime_date': rt.overtime_date,
                    'borrow_times': self.borrow_times+1,
                    })
                keeper = self.sudo().keeper_id.login.split("@")[0]
                # print('借书人')
                # print(keeper)
                # print(self.keeper_id)
                # print(user.id)
                overtime_date = rt.overtime_date[:10]
                title = ("借书成功:")
                markdown = ("## 借书成功:\n- 书名: 《%s》\n- 请于 %s 前至该楼层管理员处归还本书，谢谢！") % (self.name, overtime_date)
                redirect = "eapp://pages/mybook/mybook?query"
                self.dingtalk_send_action_card_message(keeper, title, markdown, redirect)
                return 'ok'
        return False
    # Return with Dingtalk authcode
    def return_book(self, authcode):
        user = self.dingtalk_get_user(authcode)
        if user and self.state=='borrowed' and (user in self.sudo().location_id.manager_ids):
            borrow = self.env['sce_library.book.borrow'].search([
                ('book_id', '=', self.id),
                ('user_id', '=', self.keeper_id.id),
                ('return_date', '=', False)
                ], order='id desc')
            # print(borrow) #sce_library.book.borrow(15,)
            if borrow:
                keeper = self.sudo().keeper_id.login.split("@")[0]
                borrow.sudo().write({
                    'return_date': fields.Datetime.context_timestamp(self, datetime.now()),
                    })
                self.sudo().write({
                    'state': 'available',
                    'keeper_id': False,
                    'borrow_date': False,
                    'overtime_date': False,
                    'resume_times':1,
                    })
                # title = _("Return a book successfully!")
                # markdown = _("## You have return a book:\n- Name: %s\n- return_date: %s") % (
                # self.name, borrow.return_date)
                # redirect = ""
                message = ("成功归还《%s》，谢谢！" % (self.name))
                # print(0)
                # print(message)
                # self.sudo().dingtalk_send_message(user.login.split("@")[0],message)
                self.sudo().dingtalk_send_message(keeper,message)
                return True
        return False

    # self代表模型本身，不代表任何记录
    @api.model
    def get_mybooks(self, user):
        # print(user)
        if user:
            domain = [('keeper_id', '=', user.id)]
            return self.env['sce_library.book'].search(domain)
        else:
            return []

    @api.model
    def create(self,vals):
        get_doban_img_url(vals)
        return super(Book,self).create(vals)

    @api.multi
    def write(self,vals):
        get_doban_img_url(vals)
        return super(Book,self).write(vals)

    @api.model
    def test_task(self):
        print('定时任务测试 哈哈哈')

    @api.model
    def reminder(self):
        # print('-----定时任务开始-----')
        domain = [('overtime_date', '!=', False)]
        records = self.env['sce_library.book'].search(domain)
        for record in records:
            overtime_date = datetime.strptime(record.sudo().overtime_date,'%Y-%m-%d')
            keeper = record.sudo().keeper_id.login.split('@')[0]
            # print(keeper)
            now = datetime.now()
            interval_day = overtime_date - now
            if interval_day.days <= 3:
                title = ("到期提醒:")
                markdown = ("## 到期提醒:\n- 书名: 《%s》\n- 请于 %s 前至该楼层管理员处还书，谢谢！") % (record.name, record.sudo().overtime_date[:10])
                redirect = "eapp://pages/mybook/mybook?query"
                self.dingtalk_send_action_card_message(keeper, title, markdown, redirect)
    # def action_publish(self):
        # # message = _("A new fault was published:\nSN:%s\nType:%s\nTitle:%s") % (self.name, self.type_id.name, self.title)
        # title = _("A new fault was published")
        # markdown = _("## %s\n- SN:%s\n- Type:%s\n- Title:%s") % (title, self.name, self.type_id.name, self.title)
        # # url = "http://cs.sce-re.com:8049/sce_designlib/fault/%d" % (self.id)
        # redirect = "/sce_designlib/fault/%d" % (self.id)
        # # url = "http://localhost:8069/sce_dingtalk/oauth/script/%s?redirect=%s" % (self._name, urllib.parse.quote(redirect),)
        # users = self.env.ref('sce_designlib.designlib_user').users
        # user_list = [user for user,domain in [user.login.split('@') for user in users] if domain=='sce-re.com']
        # for i in range(int(len(user_list)/20)+1):
            # send_list = user_list[i*20:i*20+20]
            # if len(send_list)>0:
                # # print(",".join(send_list))
                # self.dingtalk_send_action_card_message(",".join(send_list), title, markdown, redirect)
        # # Test
        # # self.dingtalk_send_action_card_message('jinz, liuzaih', title, markdown, redirect)
        # self.state = 'published'

    # def action_cancel_publish(self):
        # self.state = 'draft'

