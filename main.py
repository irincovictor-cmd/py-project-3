"""RoomReserve — offline classroom and facility reservation desktop application."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path
from datetime import date, timedelta
from service import RoomReserve, BookingError

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / 'roomreserve.db'

class App:
    def __init__(self, root, db_path=DB_PATH):
        self.root = root
        self.api = RoomReserve(db_path)
        self.user = None
        root.title('RoomReserve | Classroom and Facility Reservations')
        root.geometry('1160x750')
        root.minsize(900, 590)
        self.style = ttk.Style(root)
        self.style.theme_use('clam')
        self.style.configure('TFrame',background='#f5f7fb')
        self.style.configure('TLabel',background='#f5f7fb',foreground='#1d2939',font=('Segoe UI',10))
        self.style.configure('Title.TLabel',font=('Segoe UI',22,'bold'))
        self.style.configure('Heading.TLabel',font=('Segoe UI',12,'bold'))
        self.style.configure('TButton',padding=(12,9),font=('Segoe UI',10))
        self.style.configure('Treeview',rowheight=31,font=('Segoe UI',10))
        self.style.configure('Treeview.Heading',font=('Segoe UI',10,'bold'))
        self.render_login()

    def clear(self):
        for child in self.root.winfo_children(): child.destroy()

    def title(self, parent, heading, subtitle=''):
        ttk.Label(parent,text=heading,style='Title.TLabel').pack(anchor='w',pady=(0,4))
        if subtitle: ttk.Label(parent,text=subtitle).pack(anchor='w',pady=(0,18))

    def alert(self, err): messagebox.showerror('RoomReserve',str(err),parent=self.root)

    def do(self, action, success='Saved successfully.', refresh=None):
        try:
            action()
        except (BookingError,ValueError) as exc:
            self.alert(exc); return
        messagebox.showinfo('RoomReserve',success,parent=self.root)
        if refresh: refresh()

    def entry(self, parent, label, value='', width=30, show=None):
        wrap=ttk.Frame(parent); wrap.pack(fill='x',pady=5)
        ttk.Label(wrap,text=label,width=17).pack(side='left')
        widget=ttk.Entry(wrap,width=width,show=show)
        widget.pack(side='left',fill='x',expand=True)
        if value: widget.insert(0,str(value))
        return widget

    def render_login(self):
        self.clear()
        bg=ttk.Frame(self.root,padding=45); bg.pack(fill='both',expand=True)
        card=ttk.Frame(bg,padding=38); card.place(relx=.5,rely=.45,anchor='center',width=460)
        self.title(card,'RoomReserve','Classroom and Facility Reservation Management')
        first=not self.api.has_users()
        if first: ttk.Label(card,text='First launch: create an administrator account.',style='Heading.TLabel').pack(anchor='w',pady=(8,10))
        username=self.entry(card,'Username')
        password=self.entry(card,'Password',show='*')
        confirm=self.entry(card,'Confirm Password',show='*') if first else None
        def submit():
            try:
                if first:
                    if password.get()!=confirm.get(): raise BookingError('Passwords do not match.')
                    self.api.create_user(None,username.get(),password.get(),'admin')
                    messagebox.showinfo('Account created','Administrator account created. Please sign in.',parent=self.root)
                    self.render_login()
                else:
                    self.user=self.api.login(username.get(),password.get())
                    self.screen('Dashboard')
            except BookingError as exc: self.alert(exc)
        ttk.Button(card,text='Create Administrator' if first else 'Sign in',command=submit).pack(fill='x',pady=(18,10))
        ttk.Button(card,text='View Public Timetable',command=lambda:self.screen('Public Timetable')).pack(fill='x')

    def screen(self, section):
        self.clear()
        shell=ttk.Frame(self.root); shell.pack(fill='both',expand=True)
        sidebar=tk.Frame(shell,bg='#202c40',width=205); sidebar.pack(side='left',fill='y');sidebar.pack_propagate(False)
        tk.Label(sidebar,text='ROOMRESERVE',bg='#202c40',fg='white',font=('Segoe UI',17,'bold'),pady=26).pack(fill='x')
        items=['Dashboard','Public Timetable','Find Availability']
        if self.user:
            items+=['My Reservations','New Reservation']
            if self.user['role']=='admin':items+=['Approvals','Manage Rooms','Manage Users']
        for item in items:
            tk.Button(sidebar,text=item,anchor='w',padx=16,pady=12,relief='flat',bd=0,
                      bg='#354661' if item==section else '#202c40',fg='white',
                      activebackground='#3c567d',activeforeground='white',
                      font=('Segoe UI',10),command=lambda s=item:self.screen(s)).pack(fill='x',padx=8,pady=2)
        tk.Button(sidebar,text='Sign out / Home',anchor='w',padx=16,pady=12,relief='flat',bd=0,
                  bg='#202c40',fg='#c8d8ed',command=self.signout).pack(side='bottom',fill='x',padx=8,pady=18)
        main=ttk.Frame(shell,padding=24);main.pack(side='left',fill='both',expand=True)
        canvas=tk.Canvas(main,highlightthickness=0,bg='#f5f7fb')
        scrollbar=ttk.Scrollbar(main,orient='vertical',command=canvas.yview)
        content=ttk.Frame(canvas,padding=(4,2,16,15))
        content.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        win=canvas.create_window((0,0),window=content,anchor='nw')
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(win,width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        methods={'Dashboard':self.dashboard,'Public Timetable':self.timetable,'Find Availability':self.availability,
                 'My Reservations':self.my_reservations,'New Reservation':self.new_reservation,
                 'Approvals':self.approvals,'Manage Rooms':self.manage_rooms,'Manage Users':self.manage_users}
        methods[section](content)

    def signout(self): self.user=None;self.render_login()

    def table(self,parent,cols,rows,heights=13):
        container=ttk.Frame(parent);container.pack(fill='both',expand=True,pady=(8,12))
        table=ttk.Treeview(container,columns=cols,show='headings',height=heights,selectmode='browse')
        for col in cols:
            table.heading(col,text=col)
            table.column(col,width=120,minwidth=85,stretch=True,anchor='w')
        scroll=ttk.Scrollbar(container,orient='vertical',command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');table.pack(side='left',fill='both',expand=True)
        for row in rows: table.insert('', 'end',values=row)
        return table

    def chosen(self,table):
        selected=table.selection()
        if not selected: raise BookingError('Please select a row first.')
        return table.item(selected[0])['values'][0]

    def dashboard(self,p):
        self.title(p,'Dashboard',('Signed in as '+self.user['username']+' ('+self.user['role']+')') if self.user else 'Public view')
        if not self.user:
            ttk.Label(p,text='Use Public Timetable to view approved bookings. Sign in to make requests.').pack(anchor='w')
            return
        rooms=self.api.rooms(); bookings=self.api.reservations(self.user['id'])
        pending=sum(x['status']=='Pending' for x in bookings)
        approved=sum(x['status']=='Approved' for x in bookings)
        stats=ttk.Frame(p);stats.pack(fill='x',pady=10)
        for name,value in [('Rooms',len(rooms)),('Pending requests',pending),('Approved bookings',approved)]:
            b=ttk.LabelFrame(stats,text=name,padding=18);b.pack(side='left',fill='x',expand=True,padx=6)
            ttk.Label(b,text=str(value),style='Title.TLabel').pack()
        ttk.Label(p,text='Recent reservation activity',style='Heading.TLabel').pack(anchor='w',pady=(20,8))
        self.table(p,['ID','Room','Date','Time','Status'],[(r['id'],r['room_code'],r['event_date'],r['start_time']+'–'+r['end_time'],r['status']) for r in bookings[:15]])

    def timetable(self,p):
        self.title(p,'Public Timetable','Approved reservations only — visible without signing in.')
        controls=ttk.Frame(p);controls.pack(fill='x')
        day=self.entry(controls,'Date (YYYY-MM-DD)',date.today().isoformat())
        def search():
            try: bookings=self.api.reservations(public=True,day=day.get().strip() or None)
            except BookingError as e:self.alert(e);return
            for child in results.winfo_children():child.destroy()
            self.table(results,['Room','Start','End','Purpose','Attendees'],[(r['room_code'],r['start_time'],r['end_time'],r['purpose'],r['attendees']) for r in bookings])
        buttons=ttk.Frame(p);buttons.pack(anchor='w',pady=6)
        ttk.Button(buttons,text='Search date',command=search).pack(side='left',padx=(0,10))
        def weekly():
            try:
                chosen=date.fromisoformat(day.get().strip())
                monday=chosen-timedelta(days=chosen.weekday())
                bookings=[]
                for offset in range(7):
                    bookings.extend(self.api.reservations(public=True,day=(monday+timedelta(days=offset)).isoformat()))
            except ValueError:
                self.alert('Date must use YYYY-MM-DD.');return
            for child in results.winfo_children():child.destroy()
            ttk.Label(results,text=f'Week: {monday.isoformat()} to {(monday+timedelta(days=6)).isoformat()}',style='Heading.TLabel').pack(anchor='w',pady=8)
            self.table(results,['Date','Room','Start','End','Purpose','Attendees'],[(r['event_date'],r['room_code'],r['start_time'],r['end_time'],r['purpose'],r['attendees']) for r in sorted(bookings,key=lambda r:(r['event_date'],r['start_time'],r['room_code']))])
        ttk.Button(buttons,text='View full week',command=weekly).pack(side='left')
        results=ttk.Frame(p);results.pack(fill='both',expand=True)
        search()

    def availability(self,p):
        self.title(p,'Find Available Rooms','Search by date, time, capacity and facility type.')
        datebox=self.entry(p,'Date',date.today().isoformat())
        start=self.entry(p,'Start (HH:MM)','08:00')
        end=self.entry(p,'End (HH:MM)','10:00')
        number=self.entry(p,'Attendees','1')
        cat=self.entry(p,'Type (or All)','All')
        results=ttk.Frame(p);results.pack(fill='both',expand=True)
        def search():
            try: rooms=self.api.available(datebox.get(),start.get(),end.get(),number.get(),cat.get().strip() or 'All')
            except BookingError as e:self.alert(e);return
            for child in results.winfo_children():child.destroy()
            ttk.Label(results,text=f'{len(rooms)} matching rooms',style='Heading.TLabel').pack(anchor='w',pady=8)
            self.table(results,['Code','Name','Type','Capacity'],[(r['code'],r['name'],r['category'],r['capacity']) for r in rooms])
        ttk.Button(p,text='Search availability',command=search).pack(anchor='w',pady=8)
        search()

    def new_reservation(self,p):
        self.title(p,'New Reservation','Requests are submitted as Pending until an administrator approves them.')
        rooms=self.api.rooms(active_only=True)
        if not rooms:
            ttk.Label(p,text='No active rooms yet. Ask an administrator to add one.').pack(anchor='w');return
        ttk.Label(p,text='Select room').pack(anchor='w')
        choices={f"{r['code']} — {r['name']} (capacity {r['capacity']})":r['id'] for r in rooms}
        room=ttk.Combobox(p,values=list(choices),state='readonly',width=55)
        room.current(0);room.pack(anchor='w',fill='x',pady=8)
        day=self.entry(p,'Date',date.today().isoformat())
        start=self.entry(p,'Start (HH:MM)','08:00')
        end=self.entry(p,'End (HH:MM)','09:00')
        purpose=self.entry(p,'Purpose')
        attendees=self.entry(p,'Attendees','1')
        def save():
            def action(): self.api.request(self.user['id'],choices[room.get()],day.get().strip(),start.get().strip(),end.get().strip(),purpose.get(),attendees.get())
            self.do(action,'Reservation request submitted.',lambda:self.screen('My Reservations'))
        ttk.Button(p,text='Submit reservation request',command=save).pack(anchor='w',pady=15)

    def my_reservations(self,p):
        self.title(p,'Reservations','Administrators see all requests; instructors see only their own.')
        bookings=self.api.reservations(self.user['id'])
        table=self.table(p,['ID','Room','Date','Time','Purpose','Attendees','Requested by','Status'],[(r['id'],r['room_code'],r['event_date'],r['start_time']+'–'+r['end_time'],r['purpose'],r['attendees'],r['requester'],r['status']) for r in bookings])
        def cancel():
            try: key=self.chosen(table)
            except BookingError as e:self.alert(e);return
            if messagebox.askyesno('Cancel reservation','Cancel selected request?',parent=self.root):
                self.do(lambda:self.api.cancel(self.user['id'],key),'Reservation cancelled.',lambda:self.screen('My Reservations'))
        ttk.Button(p,text='Cancel selected reservation',command=cancel).pack(anchor='w',pady=8)

    def approvals(self,p):
        self.title(p,'Reservation Approvals','Overlapping pending requests cannot both be approved.')
        rows=self.api.reservations(self.user['id'],status='Pending')
        table=self.table(p,['ID','Room','Date','Start','End','Purpose','Attendees','Instructor'],[(r['id'],r['room_code'],r['event_date'],r['start_time'],r['end_time'],r['purpose'],r['attendees'],r['requester']) for r in rows])
        buttons=ttk.Frame(p);buttons.pack(anchor='w')
        def review(approve):
            try:key=self.chosen(table)
            except BookingError as e:self.alert(e);return
            note=simpledialog.askstring('Review note','Optional approval/rejection note:',parent=self.root)
            if note is None:return
            self.do(lambda:self.api.review(self.user['id'],key,approve,note),'Request reviewed.',lambda:self.screen('Approvals'))
        ttk.Button(buttons,text='Approve selected',command=lambda:review(True)).pack(side='left',padx=(0,10))
        ttk.Button(buttons,text='Reject selected',command=lambda:review(False)).pack(side='left')

    def manage_rooms(self,p):
        self.title(p,'Manage Rooms','Room codes must be unique. Disabling a room prevents new bookings.')
        rooms=self.api.rooms()
        table=self.table(p,['ID','Code','Name','Type','Capacity','Active'],[(r['id'],r['code'],r['name'],r['category'],r['capacity'],'Yes' if r['active'] else 'No') for r in rooms],8)
        form=ttk.LabelFrame(p,text='Add Room',padding=12);form.pack(fill='x',pady=8)
        code=self.entry(form,'Room code','LAB-101')
        name=self.entry(form,'Room name')
        category=self.entry(form,'Type','Classroom')
        cap=self.entry(form,'Capacity','40')
        def add():self.do(lambda:self.api.add_room(self.user['id'],code.get(),name.get(),category.get(),cap.get()),'Room added.',lambda:self.screen('Manage Rooms'))
        row=ttk.Frame(p);row.pack(anchor='w',pady=6)
        ttk.Button(row,text='Add Room',command=add).pack(side='left',padx=(0,10))
        def fill():
            try: key=self.chosen(table)
            except BookingError as e:self.alert(e);return
            room=next(r for r in rooms if r['id']==key)
            for widget,value in [(code,room['code']),(name,room['name']),(category,room['category']),(cap,room['capacity'])]:
                widget.delete(0,'end');widget.insert(0,str(value))
        def edit():
            try:key=self.chosen(table)
            except BookingError as e:self.alert(e);return
            self.do(lambda:self.api.edit_room(self.user['id'],key,code.get(),name.get(),category.get(),cap.get()),'Room updated.',lambda:self.screen('Manage Rooms'))
        ttk.Button(row,text='Load selected for edit',command=fill).pack(side='left',padx=(0,10))
        ttk.Button(row,text='Save room changes',command=edit).pack(side='left',padx=(0,10))
        def toggle(active):
            try:key=self.chosen(table)
            except BookingError as e:self.alert(e);return
            self.do(lambda:self.api.set_room_active(self.user['id'],key,active),'Room availability updated.',lambda:self.screen('Manage Rooms'))
        ttk.Button(row,text='Enable selected',command=lambda:toggle(True)).pack(side='left',padx=(0,10))
        ttk.Button(row,text='Disable selected',command=lambda:toggle(False)).pack(side='left')

    def manage_users(self,p):
        self.title(p,'Manage Users','Administrators can create instructor and additional administrator accounts.')
        users=self.api.users(self.user['id'])
        self.table(p,['ID','Username','Role','Active'],[(r['id'],r['username'],r['role'],'Yes' if r['active'] else 'No') for r in users],7)
        form=ttk.LabelFrame(p,text='New Account',padding=12);form.pack(fill='x',pady=8)
        username=self.entry(form,'Username')
        password=self.entry(form,'Password',show='*')
        ttk.Label(form,text='Role').pack(anchor='w')
        role=ttk.Combobox(form,values=['instructor','admin'],state='readonly');role.current(0);role.pack(anchor='w')
        ttk.Button(p,text='Create Account',command=lambda:self.do(lambda:self.api.create_user(self.user['id'],username.get(),password.get(),role.get()),'Account created.',lambda:self.screen('Manage Users'))).pack(anchor='w',pady=9)


def main():
    root=tk.Tk()
    try: App(root)
    except Exception as exc:
        messagebox.showerror('Startup error',str(exc),parent=root)
        root.destroy();return
    root.mainloop()

if __name__=='__main__':main()
