# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
from odoo.addons.website.controllers.main import QueryURL
from datetime import datetime, timedelta
PPG = 20  # Fault Per Page
BORROWDAYS = 14

# from odoo.addons.website.controllers.main import QueryURL

class SceLibraryBookController(http.Controller):
    @http.route('/sce_library/book/<model("sce_library.book"):book>', auth="user", website=True)
    def book_view(self, book, **kw):
        return http.request.render('sce_library.book_view',{
            'book': book,
            })

    @http.route([
        '/sce_library/book',
        '/sce_library/book/page/<int:page>',
        '/sce_library/book/<int:bookid>',
        # '/sce_library/category/<model("product.public.category"):category>',
        # '/sce_library/category/<model("product.public.category"):category>/page/<int:page>'
    ], type='http', auth="user", website=True)
    def book_list(self, page=0, category=None, search='', ppg=False, **post):
        if ppg:
            try:
                ppg = int(ppg)
            except ValueError:
                ppg = PPG
            post["ppg"] = ppg
        else:
            ppg = PPG

        attrib_list = request.httprequest.args.getlist('attrib')
        attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
        attributes_ids = {v[0] for v in attrib_values}
        attrib_set = {v[1] for v in attrib_values}

        # domain = self._get_search_domain(search, category, attrib_values)
        domain=[('state','=','available'),]

        keep = QueryURL('/sce_library/book', category=category and int(category), search=search, attrib=attrib_list, order=post.get('order'))

        request.context = dict(request.context, pricelist=False, partner=request.env.user.partner_id)

        url = "/sce_library/book"
        if search:
            post["search"] = search
        if post.get('book_tag'):
            domain.append(('tag_ids', '=', int(post['book_tag'])))

        # print(domain)
        Book = request.env['sce_library.book']

        parent_category_ids = []

        book_count = Book.search_count(domain)
        pager = request.website.pager(url=url, total=book_count, page=page, step=ppg, scope=7, url_args=post)
        books = Book.search(domain, limit=ppg, offset=pager['offset'], order="name asc")

        values = {
            'search': search,
            # 'category': category,
            'pager': pager,
            'books': books,
            'search_count': book_count,  # common for all searchbox
            'rows': PPG,
            'keep': keep,
            'no_footer': True,
        }
        return request.render("sce_library.books", values)

    @http.route([
        '/rpc/sce_library/book/borrow',
    ], auth="public", type='json', website=True, csrf=False)
    def rpc_book_borrow(self, code=None, authcode=None, **post):
        if code and authcode:
            domain = [('code','=',code)]
            book = request.env['sce_library.book'].search(domain)
            if book:
                rt = book.borrow(authcode)
                if rt=='ok':
                    return {'status': 'ok'}
                elif rt=='overlimit':
                    return {'status': 'failed', 'reason': 'overlimit'}
                elif rt=='borrowed':
                    return {'status': 'failed', 'reason': 'borrowed'}
        return {'status': 'failed', 'reason':'unknown'}

    @http.route([
        '/rpc/sce_library/book',
        '/rpc/sce_library/book/<int:bookid>',
        '/rpc/sce_library/book/code/<bookcode>',
    ], auth="public", type='json', website=True, csrf=False)
    def rpc_book_list(self, search='', bookid=None, bookcode=None, limit=PPG, kind_id=0, loc_id=0, order=None, keyword=None, **post):
        Book = request.env['sce_library.book']
        Kind = request.env['sce_library.book.kind']
        Location = request.env['sce_library.location']

        if bookid or bookcode:
            book = None
            if bookid:
                book = Book.browse(bookid)
            else:
                book = Book.search([('code','=',bookcode)]).sudo()
            bookinfo = None
            if book:
                bookinfo = {
                        'id': book.id,
                        'kind': book.kind_id.name,
                        'name': book.name,
                        'author': book.author,
                        'publisher': book.publisher,
                        'location': book.location_id.name,
                        'code': book.code,
                        'isbn': book.isbn,
                        'state': book.state,
                        'image': book.image_url,
                        }
                if book.state == 'available':
                    bookinfo.update({
                            'borrow_date': fields.Date.context_today(book, datetime.now()),
                            'return_date': fields.Date.context_today(book, datetime.now()+timedelta(days=BORROWDAYS)),
                            })
                elif book.state == 'borrowed':
                    bookinfo.update({
                            'keeper': book.keeper_id.name,
                            'borrow_date': book.borrow_date,
                            'overtime_date': book.overtime_date,
                            'return_date': fields.Date.context_today(book, datetime.now()),
                            })
            result = { 'bookinfo': bookinfo }
        else: 
            domain=[('state','=','available'),]
            if kind_id:
                domain.append(('kind_id','=',kind_id))
            if loc_id:
                domain.append(('location_id','=',loc_id))
            if keyword and keyword.strip()!="":
                domain.append(('name', 'ilike', keyword))
            if order=='name':
                books = Book.search(domain, limit=limit, order='name')
            else:
                books = Book.search(domain, limit=limit, order="borrow_times desc")
            book_count = Book.search_count(domain)
            book_values = [
                    {
                        'id': book.id,
                        'name': book.name,
                        'author': book.author,
                        'publisher': book.publisher,
                        'location': book.location_id.name,
                        'image': book.image_url,
                    }
                    for book in books]
            result = {
                'search_count': book_count,  # common for all searchbox
                'kinds': [ {'id':kind.id,'name':kind.name} for kind in Kind.search([]) ],
                'locations': [ {'id':loc.id,'name':loc.name} for loc in Location.search([]) ],
                'books': book_values,
            }
        return result


    @http.route([
        '/rpc/sce_library/book/mybook',
    ], auth="public", type='json', website=True, csrf=False)
    def rpc_book_mybook(self, authcode=None, **kwargs):
        mybook_values = []
        if authcode:
            user = request.env['sce_library.book'].dingtalk_get_user(authcode)
            mybooks = request.env['sce_library.book'].get_mybooks(user)
            mybook_values = [
                    {
                        'id': book.id,
                        'name': book.name,
                        'author': book.author,
                        'publisher': book.publisher,
                        'location': book.location_id.name,
                        'kind': book.kind_id.name,
                        'borrow_date': book.borrow_date,
                        'overtime_date': book.overtime_date,
                        'image': book.image_url,
                    }
                    for book in mybooks]
            is_manager = False
            if user.library_manage_loc_ids:
                is_manager = True
            return {'mybooks': mybook_values, 'is_manager': is_manager}

    @http.route([
        '/rpc/sce_library/book/return',
    ], auth="public", type='json', website=True, csrf=False)
    def rpc_book_return(self, code=None, authcode=None, **post):
        if code and authcode:
            domain = [('code','=',code)]
            book = request.env['sce_library.book'].search(domain)
            if book:
                rt = book.return_book(authcode)
                if rt:
                    return {'status': 'ok'}
        return {'status': 'faild'}
