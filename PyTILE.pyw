from Libs.utils import *
from Libs.setutils import *
from Libs.trace import setup_trace
from Libs import GRP, Tilesets, TBL
from Libs.Tilesets import TILETYPE_GROUP, TILETYPE_MEGA, TILETYPE_MINI, HEIGHT_LOW, HEIGHT_MID, HEIGHT_HIGH
from Libs.FlowView import FlowView
from Libs.MaskCheckbutton import MaskCheckbutton
from Libs.MaskedRadiobutton import MaskedRadiobutton
from Libs.ScrolledListbox import ScrolledListbox
from Libs.analytics import *

from Tkinter import *
from tkMessageBox import *
import tkFileDialog,tkColorChooser
from Libs.stylized import *

from PIL import Image
from PIL import ImageTk

import sys

from thread import start_new_thread
from math import ceil,floor
import optparse, os, webbrowser, sys

LONG_VERSION = 'v%s' % VERSIONS['PyTILE']
PYTILE_SETTINGS = Settings('PyTILE', '1')

TILE_CACHE = {}

def tip(o, t, h):
	o.tooltip = Tooltip(o, t + ':\n  ' + h, mouse=True)
PAL = [0]

MEGA_EDIT_MODE_MINI			 = 0
MEGA_EDIT_MODE_FLIP			 = 1
MEGA_EDIT_MODE_HEIGHT		 = 2
MEGA_EDIT_MODE_WALKABILITY	 = 3
MEGA_EDIT_MODE_VIEW_BLOCKING = 4
MEGA_EDIT_MODE_RAMP			 = 5

STYLE_BOXES					= 0
STYLE_DOTS					= 1
STYLE_BOXES_AND_DOTS		= 2

class MegaEditorView(Frame):
	def __init__(self, parent, delegate, megatile_id=None, palette_editable=False, pytile=None):
		Frame.__init__(self, parent)

		self.parent = pytile
		self.delegate = delegate
		self.megatile_id = megatile_id
		self.palette_editable = palette_editable
		self.edit_mode = IntVar()
		self.edit_mode.set(PYTILE_SETTINGS.mega_edit.get('mode', MEGA_EDIT_MODE_MINI))
		self.edit_mode.trace('w', self.edit_mode_updated)
		if hasattr(self.delegate, 'mega_edit_mode_updated'):
			self.delegate.mega_edit_mode_updated(self.edit_mode.get())
		self.minitile_n = 0
		self.last_click = None
		self.toggle_on = None
		self.enabled = True
		self.disable = []

		self.minitile = IntegerVar(0,[0,0],callback=lambda id: self.change(None, int(id)))
		self.height = IntVar()
		self.height.set(PYTILE_SETTINGS.mega_edit.get('height', 1))
		self.height.trace('w', self.height_updated)

		self.active_tools = None

		frame = Frame(self)
		tools = ['Minitile (m)','Flip (f)','Height (h)','Walkable (w)','Block view (b)','Ramp? (r)']
		d = DropDown(frame, self.edit_mode, tools, width=15)
		self.disable.append(d)
		d.pack(side=TOP, padx=5)
		bind = [
			('m',MEGA_EDIT_MODE_MINI),
			('f',MEGA_EDIT_MODE_FLIP),
			('h',MEGA_EDIT_MODE_HEIGHT),
			('w',MEGA_EDIT_MODE_WALKABILITY),
			('b',MEGA_EDIT_MODE_VIEW_BLOCKING),
			('r',MEGA_EDIT_MODE_RAMP)
		]
		def set_edit_mode(mode):
			if not self.enabled:
				return
			self.edit_mode.set(mode)
		for b,m in bind:
			self.delegate.bind(b, lambda e,m=m: set_edit_mode(m))
		self.canvas = Canvas(frame, width=96, height=96, background='#000000')
		def mouse_to_mini(e):
			if e.x < 1 or e.x > 96 or e.y < 1 or e.y > 96:
				return None
			return (e.y - 1) / 24 * 4 + (e.x - 1) / 24
		def click(e, mouseButton, fill=False):
			mini = mouse_to_mini(e)
			if (fill):
				self.last_click = mini
				self.fill_minitiles(self.last_click, mouseButton)
				return

			if mini != None:
				self.last_click = mini
				self.click_minitile(self.last_click, mouseButton)
		def move(e, mouseButton):
			mini = mouse_to_mini(e)
			if mini != None and mini != self.last_click:
				self.last_click = mini
				self.click_minitile(mini, mouseButton)
		def release(_):
			self.last_click = None
			self.toggle_on = None
			if hasattr(self.parent, "show_minitiles"):
				if self.parent.show_minitiles.get():
					self.parent.palette.draw_tiles(force=True)

		self.canvas.bind('<Button-1>', lambda e:click(e, 0))
		self.canvas.bind('<Button-2>', lambda e:click(e, 1))
		self.canvas.bind('<Button-3>', lambda e:click(e, 2))
		self.canvas.bind('<Control-Button-1>', lambda e:click(e, 0, True))
		self.canvas.bind('<Control-Button-2>', lambda e:click(e, 1, True))
		self.canvas.bind('<Control-Button-3>', lambda e:click(e, 2, True))
		self.canvas.bind('<B1-Motion>', lambda e:move(e, 0))
		self.canvas.bind('<B2-Motion>', lambda e:move(e, 1))
		self.canvas.bind('<B3-Motion>', lambda e:move(e, 2))
		self.canvas.bind('<ButtonRelease-1>', release)
		self.canvas.bind('<ButtonRelease-2>', release)
		self.canvas.bind('<ButtonRelease-3>', release)
		self.canvas.pack(side=TOP)
		self.mini_tools = Frame(frame)
		e = Frame(self.mini_tools)
		Label(e, text='ID:').pack(side=LEFT)
		f = Entry(e, textvariable=self.minitile, font=couriernew, width=5)
		tip(f, 'MiniTile ID', 'ID for the selected MiniTile in the current MegaTile')
		self.disable.append(f)
		f.pack(side=LEFT, padx=2)
		i = PhotoImage(file=os.path.join(BASE_DIR,'Images','find.gif'))
		b = Button(e, image=i, width=20, height=20, command=self.choose)
		b.image = i
		self.disable.append(b)
		b.pack(side=LEFT, padx=2)
		i = PhotoImage(file=os.path.join(BASE_DIR,'Images','edit.gif'))
		b = Button(e, image=i, width=20, height=20, command=self.editor)
		b.image = i
		self.disable.append(b)
		b.pack(side=LEFT, padx=2)
		e.pack(fill=X)
		self.mini_tools.pack(side=TOP, pady=(3,0))
		self.mini_tools.pack_forget()
		self.height_tools = Frame(frame)
		self.disable.append(d)
		self.height_tools.pack(side=TOP, pady=(3,0))
		self.height_tools.pack_forget()
		frame.pack(side=LEFT, fill=Y)

		self.update_mini_range()
		self.update_tools()
		self.load_megatile()

	def editor(self):
		minitile_image_id = self.delegate.tileset.vx4.graphics[self.megatile_id][self.minitile_n][0]
		MiniEditor(self.delegate, minitile_image_id)

	def set_enabled(self, enabled):
		self.enabled = enabled
		state = NORMAL if enabled else DISABLED
		for w in self.disable:
			w['state'] = state

	def update_mini_range(self):
		size = 0
		if self.delegate.tileset:
			size = len(self.delegate.tileset.vr4.images)-1
		self.minitile.setrange([0,size])

	def update_tools(self):
		if self.active_tools:
			self.active_tools.pack_forget()
			self.active_tools = None
		mode = self.edit_mode.get()
		if mode == MEGA_EDIT_MODE_MINI:
			self.mini_tools.pack()
			self.active_tools = self.mini_tools
		elif mode == MEGA_EDIT_MODE_HEIGHT:
			self.height_tools.pack()
			self.active_tools = self.height_tools

	def edit_mode_updated(self, *_):
		self.delegate.palette.canvas.focus_force()
		self.update_tools()
		self.draw_edit_mode()
		mode = self.edit_mode.get()
		PYTILE_SETTINGS.mega_edit.mode = mode
		if (self.parent.show_minitiles.get()):
			self.parent.palette.draw_tiles(force=True)
		if (hasattr(self, "parent") and self.parent.show_minitiles.get()):
			self.parent.palette.draw_tiles(force=True)

	def height_updated(self, *_):
		PYTILE_SETTINGS.mega_edit.height = self.height.get()

	def draw_border(self, minitile_n, color='#FFFFFF'):
		x = 3 + 24 * (minitile_n % 4)
		y = 3 + 24 * (minitile_n / 4)

		style = STYLE_BOXES
		if hasattr(self.parent, "style"):
			style = self.parent.style.get()
		if style == STYLE_BOXES or style == STYLE_BOXES_AND_DOTS:
			self.canvas.create_rectangle(x, y, x+21,y+21, outline=color, tags='mode')
		if style == STYLE_DOTS or style == STYLE_BOXES_AND_DOTS:
			self.canvas.create_rectangle(x+9,y+9, x+13,y+13, outline="", fill=color, tags='mode')


	def draw_selection(self):
		self.draw_border(self.minitile_n)

	def draw_height(self):
		for n in xrange(16):
			flags = self.delegate.tileset.vf4.flags[self.megatile_id][n]
			color = '#FF0000'
			if flags & HEIGHT_MID:
				color = '#FF7F00'
			elif flags & HEIGHT_HIGH:
				color = '#FFFF00'
			self.draw_border(n, color)
	def draw_walkability(self):
		for n in xrange(16):
			flags = self.delegate.tileset.vf4.flags[self.megatile_id][n]
			self.draw_border(n, '#00FF00' if flags & 1 else '#FF0000')
	def draw_blocking(self):
		for n in xrange(16):
			flags = self.delegate.tileset.vf4.flags[self.megatile_id][n]
			self.draw_border(n, '#FF0000' if flags & 8 else '#00FF00')
	def draw_ramp(self):
		for n in xrange(16):
			flags = self.delegate.tileset.vf4.flags[self.megatile_id][n]
			self.draw_border(n, '#00FF00' if flags & 16 else '#FF0000')
	def draw_edit_mode(self):
		self.canvas.delete('mode')
		if not self.delegate.tileset or self.megatile_id == None:
			return
		mode = self.edit_mode.get()
		if mode == MEGA_EDIT_MODE_MINI:
			self.draw_selection()
		elif mode == MEGA_EDIT_MODE_HEIGHT:
			self.draw_height()
		elif mode == MEGA_EDIT_MODE_WALKABILITY:
			self.draw_walkability()
		elif mode == MEGA_EDIT_MODE_VIEW_BLOCKING:
			self.draw_blocking()
		elif mode == MEGA_EDIT_MODE_RAMP:
			self.draw_ramp()

	def click_selection(self, minitile_n):
		self.minitile_n = minitile_n
		self.minitile.set(self.delegate.tileset.vx4.graphics[self.megatile_id][minitile_n][0], silence=True)
		self.draw_edit_mode()
	def click_flipped(self, minitile_n):
		megatile = list(self.delegate.tileset.vx4.graphics[self.megatile_id])
		minitile = megatile[minitile_n]
		megatile[minitile_n] = (minitile[0], not minitile[1])
		self.delegate.tileset.vx4.set_tile(self.megatile_id, megatile)
		self.redraw_delegate()
		self.draw()
		self.mark_edited()
	def click_height(self, minitile_n, mouseButton):
		flags = self.delegate.tileset.vf4.flags[self.megatile_id][minitile_n]
		new_flags = flags & ~(HEIGHT_MID | HEIGHT_HIGH)
		new_flags |= [HEIGHT_LOW,HEIGHT_HIGH,HEIGHT_MID][mouseButton]
		if new_flags != flags:
			self.delegate.tileset.vf4.flags[self.megatile_id][minitile_n] = new_flags
			self.draw_edit_mode()
			self.mark_edited()
	def click_flag(self, minitile_n, flag, mouseButton):
		if mouseButton == 1:
			self.fill_flag(minitile_n, flag, mouseButton)
			return

		if mouseButton == 0:
			self.delegate.tileset.vf4.flags[self.megatile_id][minitile_n] |= flag
		else:
			self.delegate.tileset.vf4.flags[self.megatile_id][minitile_n] &= ~flag
		self.draw_edit_mode()
		self.mark_edited()

	def click_minitile(self, minitile_n, mouseButton, in_tileset_view=False):
		if not self.delegate.tileset or self.megatile_id == None:
			return

		mode = self.edit_mode.get()
		if mode == MEGA_EDIT_MODE_MINI and not in_tileset_view:
			self.click_selection(minitile_n)
		elif mode == MEGA_EDIT_MODE_FLIP and not in_tileset_view:
			self.click_flipped(minitile_n)
		elif mode == MEGA_EDIT_MODE_HEIGHT:
			self.click_height(minitile_n, mouseButton)
		elif mode == MEGA_EDIT_MODE_WALKABILITY:
			self.click_flag(minitile_n, 1, mouseButton)
		elif mode == MEGA_EDIT_MODE_VIEW_BLOCKING:
			self.click_flag(minitile_n, 8, mouseButton)
		elif mode == MEGA_EDIT_MODE_RAMP:
			self.click_flag(minitile_n, 16, mouseButton)

	def fill_height(self, mouseButton):
		edited = False
		for n in xrange(16):
			flags = self.delegate.tileset.vf4.flags[self.megatile_id][n]
			new_flags = flags & ~(HEIGHT_MID | HEIGHT_HIGH)
			new_flags |= [HEIGHT_LOW,HEIGHT_HIGH,HEIGHT_MID][mouseButton]
			if new_flags != flags:
				self.delegate.tileset.vf4.flags[self.megatile_id][n] = new_flags
				edited = True
		if edited:
			self.draw_edit_mode()
			self.mark_edited()
	def fill_flag(self, minitile_n, flag, mouseButton):
		originalState = self.delegate.tileset.vf4.flags[self.megatile_id][minitile_n] & flag
		for n in xrange(16):
			if mouseButton == 0 or (mouseButton == 1 and originalState != flag):
				self.delegate.tileset.vf4.flags[self.megatile_id][n] |= flag
			else:
				self.delegate.tileset.vf4.flags[self.megatile_id][n] &= ~flag
		self.draw_edit_mode()
		self.mark_edited()
	def fill_minitiles(self, minitile_n, mouseButton):
		if not self.delegate.tileset or self.megatile_id == None:
			return
		mode = self.edit_mode.get()
		if mode == MEGA_EDIT_MODE_HEIGHT:
			self.fill_height(mouseButton)
		elif mode == MEGA_EDIT_MODE_WALKABILITY:
			self.fill_flag(minitile_n, 1, mouseButton)
		elif mode == MEGA_EDIT_MODE_VIEW_BLOCKING:
			self.fill_flag(minitile_n, 8, mouseButton)
		elif mode == MEGA_EDIT_MODE_RAMP:
			self.fill_flag(minitile_n, 16, mouseButton)

	def draw_minitiles(self):
		self.canvas.delete('tile')
		self.canvas.images = []
		if not self.delegate.tileset or self.megatile_id == None:
			return
		for n,m in enumerate(self.delegate.tileset.vx4.graphics[self.megatile_id]):
			self.canvas.images.append(self.delegate.get_tile(m))
			self.canvas.create_image(2 + 24 * (n % 4), 2 + 24 * (n / 4), anchor=NW, image=self.canvas.images[-1], tags='tile')

	def draw(self):
		self.draw_minitiles()
		self.draw_edit_mode()

	def load_megatile(self):
		if self.delegate.tileset and self.megatile_id != None:
			self.minitile.set(self.delegate.tileset.vx4.graphics[self.megatile_id][self.minitile_n][0], silence=True)
		else:
			self.minitile.set(0, silence=True)
		self.draw()

	def set_megatile(self, megatile_id):
		self.megatile_id = megatile_id
		self.load_megatile()

	def redraw_delegate(self):
		if self.megatile_id in TILE_CACHE:
			del TILE_CACHE[self.megatile_id]
		if hasattr(self.delegate, 'draw_group'):
			self.delegate.draw_group()
	def mark_edited(self):
		self.delegate.mark_edited()
	def change(self, tiletype, minitile_id):
		if tiletype == TILETYPE_MINI:
			self.minitile.set(minitile_id, silence=True)
		elif tiletype != None:
			return
		megatile = list(self.delegate.tileset.vx4.graphics[self.megatile_id])
		minitile = megatile[self.minitile_n]
		megatile[self.minitile_n] = (minitile_id, minitile[1])
		self.delegate.tileset.vx4.set_tile(self.megatile_id, megatile)
		self.redraw_delegate()
		self.draw()
		self.mark_edited()
	def choose(self):
		TilePalette(self.delegate, TILETYPE_MINI, self.delegate.tileset.vx4.graphics[self.megatile_id][self.minitile_n][0], self, editing=self.palette_editable)

class MegaEditor(PyMSDialog):
	def __init__(self, parent, id):
		self.id = id
		self.tileset = parent.tileset
		self.get_tile = parent.get_tile
		self.edited = False
		PyMSDialog.__init__(self, parent, 'MegaTile Editor [%s]' % id)

	def widgetize(self):
		self.editor = MegaEditorView(self, self, self.id)
		self.editor.pack(side=TOP, padx=3, pady=(3,0))
		ok = Button(self, text='Ok', width=10, command=self.ok)
		ok.pack(side=BOTTOM, padx=3, pady=3)
		return ok

	def mark_edited(self):
		self.edited = True

	def megaload(self):
		self.editor.draw()

	def ok(self):
		if self.edited:
			if self.editor.megatile_id in TILE_CACHE:
				del TILE_CACHE[self.editor.megatile_id]
			if hasattr(self.parent, 'megaload'):
				self.parent.megaload()
			if hasattr(self.parent, 'draw_tiles'):
				self.parent.draw_tiles(force=True)
			if hasattr(self.parent, 'mark_edited'):
				self.parent.mark_edited()
		PyMSDialog.ok(self)

class Placeability(PyMSDialog):
	def __init__(self, parent, id=0):
		self.id = id
		self.canvass = []
		self.groups = []
		self.tileset = parent.tileset
		self.get_tile = parent.get_tile
		self.selecting = None
		self.width = 0
		PyMSDialog.__init__(self, parent, 'Doodad Placeability [%s]' % id, resizable=(False,False))

	def widgetize(self):
		f = Frame(self)
		ty = -1
		for n,g in enumerate(self.tileset.cv5.groups[1024:]):
			if g[9] == self.id and ty == -1:
				self.width,h,ty = g[10],g[11],g[11]-1
				if n + h > len(self.tileset.cv5.groups):
					h = len(self.tileset.cv5.groups) - n - 1
					ty = h-1
				for y in range(h):
					self.groups.append([])
					self.canvass.append(Canvas(f, width=self.width * 33-1, height=32))
					self.canvass[-1].grid(sticky=E+W, column=0, row=y*2, columnspan=self.width)
					self.canvass[-1].images = []
					for x in range(self.width):
						c = self.tileset.dddata.doodads[self.id][x + y * self.width]
						if not y:
							t = 'tile%s,%s' % (x,y)
							self.canvass[-1].images.append(Tilesets.megatile_to_photo(self.tileset, g[13][x]))
							self.canvass[-1].create_image(x * 33 + 18, 18, image=self.canvass[-1].images[-1], tags=t)
							self.canvass[-1].tag_bind(t, '<Double-Button-1>', lambda e,p=(x,y): self.select(p))
						self.groups[-1].append(IntegerVar(c,[0,len(self.tileset.cv5.groups)]))
						Entry(f, textvariable=self.groups[-1][-1], width=1, font=couriernew, bd=0).grid(sticky=E+W, column=x, row=y*2+1, padx=x%2)
			elif ty > 0:
				for x in range(self.width):
					t = 'tile%s,%s' % (x,y)
					self.canvass[h-ty].images.append(Tilesets.megatile_to_photo(self.tileset, g[13][x]))
					self.canvass[h-ty].create_image(x * 33 + 18, 18, image=self.canvass[h-ty].images[-1], tags=t)
					self.canvass[h-ty].tag_bind(t, '<Double-Button-1>', lambda e,p=(x,h-ty): self.select(p))
				ty -= 1
				if not ty:
					break
		f.pack(padx=5,pady=5)

	def select(self, p):
		self.selecting = p
		TilePalette(self, 0, self.groups[p[1]][p[0]].get())

	def change(self, t, id):
		self.groups[self.selecting[1]][self.selecting[0]].set(id)
		self.selecting = None

	def cancel(self, e=None):
		self.ok(self)

	def ok(self, e=None):
		edited = False
		for y,l in enumerate(self.groups):
			for x,g in enumerate(l):
				n = x + y * self.width
				value = g.get()
				old_value = self.tileset.dddata.doodads[self.id][n]
				if value != old_value:
					self.tileset.dddata.doodads[self.id][n] = value
					edited = True
		if edited:
			self.parent.mark_edited()
		PyMSDialog.ok(self)

class MiniEditor(PyMSDialog):
	def __init__(self, parent, id, colors=[0,0]):
		self.colors = colors
		self.click = None
		self.select = False
		self.id = id
		self.edited = True
		PyMSDialog.__init__(self, parent, 'MiniTile Editor [%s]' % id, resizable=(False,False))

	def widgetize(self):
		self.canvas = Canvas(self, width=202, height=114)
		self.canvas.pack(padx=3,pady=3)
		self.canvas.bind('<ButtonRelease-1>', self.release)
		self.canvas.bind('<ButtonRelease-2>', self.release)
		self.canvas.bind('<ButtonRelease-3>', self.release)
		self.canvas.bind('<Motion>', self.motion)
		self.canvas.bind('<B1-Motion>', self.motion)
		self.canvas.bind('<B2-Motion>', self.motion)
		self.canvas.bind('<B3-Motion>', self.motion)
		d = self.parent.tileset.vr4.images[self.id]
		self.colors[0] = d[0][0]
		self.indexs = []
		for y,p in enumerate(d):
			self.indexs.append(list(p))
			for x,i in enumerate(p):
				cx,cy,c = x * 10 + 2, y * 10 + 2, '#%02x%02x%02x' % tuple(self.parent.tileset.wpe.palette[i])
				t = 'tile%s,%s' % (x,y)
				self.canvas.create_rectangle(cx, cy, cx+10, cy+10, fill=c, outline=c, tags=t)
				self.canvas.tag_bind(t, '<Button-1>', lambda e,p=(x,y),c=0: self.color(p,c))
				self.canvas.tag_bind(t, '<Button-2>', lambda e,p=(x,y),c=1: self.color(p,c))
				self.canvas.tag_bind(t, '<Button-3>', lambda e,p=(x,y),c=1: self.color(p,c))
				cx,cy = x + 32,y + 90
				self.canvas.create_rectangle(cx, cy, cx+2, cy+2, fill=c, outline=c, tags='scale%s,%s' % (x,y))
		self.canvas.create_rectangle(90, 2, 202, 114, fill='#000000', outline='#000000')
		for n,i in enumerate(self.parent.tileset.wpe.palette):
			cx,cy,c = (n % 16) * 7 + 91, (n / 16) * 7 + 3, '#%02x%02x%02x' % tuple(i)
			t = 'pal%s' % n
			self.canvas.create_rectangle(cx, cy, cx+5, cy+5, fill=c, outline=c, tags=t)
			c = '#%02x%02x%02x' % tuple(self.parent.tileset.wpe.palette[self.colors[1]])
			self.canvas.tag_bind(t, '<Button-1>', lambda e,p=n,c=0: self.pencolor(p,c))
			self.canvas.tag_bind(t, '<Button-2>', lambda e,p=n,c=1: self.pencolor(p,c))
			self.canvas.tag_bind(t, '<Button-3>', lambda e,p=n,c=1: self.pencolor(p,c))
		c = '#%02x%02x%02x' % tuple(self.parent.tileset.wpe.palette[self.colors[1]])
		self.canvas.create_rectangle(10, 98, 26, 114, fill=c, outline=c, tags='bg')
		c = '#%02x%02x%02x' % tuple(self.parent.tileset.wpe.palette[self.colors[0]])
		self.canvas.create_rectangle(2, 90, 18, 106, fill=c, outline=c, tags='fg')
		self.eyedropper = PhotoImage(file=os.path.join(BASE_DIR,'Images','eyedropper.gif'))
		self.canvas.create_image(56, 101, image=self.eyedropper, tags='eyedropper')
		self.canvas.tag_bind('eyedropper', '<Button-1>', self.dropper)
		b = Frame(self)
		ok = Button(b, text='Ok', width=10, command=self.ok)
		ok.pack(side=LEFT, padx=2)
		Button(b, text='Cancel', width=10, command=self.cancel).pack(side=LEFT)
		b.pack(pady=3)
		return ok

	def dropper(self, e=None):
		if self.select:
			self.canvas.delete('dropbd')
		else:
			self.canvas.create_rectangle(45, 90, 66, 111, outline='#000000', tags='dropbd')
		self.select = not self.select

	def release(self, e):
		self.click = None

	def motion(self, e):
		o = self.canvas.find_overlapping(e.x,e.y,e.x,e.y)
		if self.click != None and o and len(o) == 1:
			t = self.canvas.gettags(o[0])
			if t and len(t) == 1 and t[0].startswith('tile'):
				self.color(tuple(int(n) for n in t[0][4:].split(',')),self.click)

	def color(self, p, c):
		if self.select:
			self.colors[c] = self.indexs[p[1]][p[0]]
			r = '#%02x%02x%02x' % tuple(self.parent.tileset.wpe.palette[self.colors[c]])
			self.canvas.itemconfig(['fg','bg'][c], fill=r, outline=r)
			self.dropper()
		else:
			self.indexs[p[1]][p[0]] = self.colors[c]
			r = '#%02x%02x%02x' % tuple(self.parent.tileset.wpe.palette[self.colors[c]])
			self.canvas.itemconfig('tile%s,%s' % p, fill=r, outline=r)
			self.canvas.itemconfig('scale%s,%s' % p, fill=r, outline=r)
			self.click = c
		self.edited = True

	def pencolor(self, p, c):
		self.colors[c] = p
		r = '#%02x%02x%02x' % tuple(self.parent.tileset.wpe.palette[p])
		self.canvas.itemconfig(['fg','bg'][c], fill=r, outline=r)

	def cancel(self):
		PyMSDialog.cancel(self)

	def ok(self):
		self.parent.tileset.vr4.set_image(self.id, self.indexs)
		self.parent.mark_edited()
		if hasattr(self.parent, 'megaload'):
			self.parent.megaload()
		elif isinstance(self.parent, TilePalette):
			TILE_CACHE.clear()
			self.parent.draw_tiles(force=True)
		PyMSDialog.ok(self)

class GraphicsImporter(PyMSDialog):
	def __init__(self, parent, tiletype=TILETYPE_GROUP, ids=None):
		self.tiletype = tiletype
		self.ids = ids
		self.tileset = parent.tileset
		self.get_tile = parent.get_tile
		title = 'Import '
		if tiletype == TILETYPE_GROUP:
			title += 'MegaTile Group'
		elif tiletype == TILETYPE_MEGA:
			title += 'MegaTile'
		elif tiletype == TILETYPE_MINI:
			title += 'MiniTile'
		title += ' Graphics'
		PyMSDialog.__init__(self, parent, title, resizable=(True,True), set_min_size=(True,True))

	def widgetize(self):
		self.replace_selections = IntVar()
		self.auto_close = IntVar()
		self.megatiles_reuse_duplicates_old = IntVar()
		self.megatiles_reuse_duplicates_new = IntVar()
		self.megatiles_reuse_null = IntVar()
		self.megatiles_null_id = IntegerVar(0,[0,len(self.tileset.vf4.flags)-1])
		self.minitiles_reuse_duplicates_old = IntVar()
		self.minitiles_reuse_duplicates_new = IntVar()
		self.minitiles_reuse_null = IntVar()
		self.minitiles_null_id = IntegerVar(0,[0,len(self.tileset.vr4.images)-1])
		self.load_settings()

		self.find = PhotoImage(file=os.path.join(BASE_DIR,'Images','find.gif'))
		frame = LabelFrame(self, text="BMP's:")
		self.graphics_list = ScrolledListbox(frame, frame_config={'bd':2, 'relief': SUNKEN}, auto_bind=self, selectmode=EXTENDED, activestyle=DOTBOX, height=3, bd=0, highlightthickness=0, exportselection=0)
		self.graphics_list.pack(side=TOP, fill=BOTH, expand=1, padx=2,pady=2)
		self.graphics_list.bind('<<ListboxSelect>>', self.update_states)
		buts = Frame(frame)
		button = Button(buts, image=self.find, width=20, height=20, command=lambda *_: self.select_paths(replace=True))
		button.pack(side=LEFT, padx=(1,0))
		button.tooltip = Tooltip(button, "Set BMP's", mouse=True)
		image = PhotoImage(file=os.path.join(BASE_DIR, 'Images','add.gif'))
		button = Button(buts, image=image, width=20, height=20, command=lambda *_: self.select_paths(replace=False))
		button.pack(side=LEFT)
		button.image = image
		button.tooltip = Tooltip(button, "Add BMP's", mouse=True)
		image = PhotoImage(file=os.path.join(BASE_DIR, 'Images','remove.gif'))
		button = Button(buts, image=image, width=20, height=20, command=self.remove_paths)
		button.pack(side=LEFT)
		button.image = image
		button.tooltip = Tooltip(button, "Remove BMP's", mouse=True)
		self.sel_buttons = [button]
		image = PhotoImage(file=os.path.join(BASE_DIR, 'Images','down.gif'))
		button = Button(buts, image=image, width=20, height=20, command=self.shift_down)
		button.pack(side=RIGHT, padx=(0,1))
		button.image = image
		button.tooltip = Tooltip(button, "Move Selections Down", mouse=True)
		self.sel_buttons.append(button)
		image = PhotoImage(file=os.path.join(BASE_DIR, 'Images','up.gif'))
		button = Button(buts, image=image, width=20, height=20, command=self.shift_up)
		button.pack(side=RIGHT)
		button.image = image
		button.tooltip = Tooltip(button, "Move Selections Up", mouse=True)
		self.sel_buttons.append(button)
		buts.pack(fill=X)
		frame.pack(side=TOP, fill=BOTH, expand=1, padx=3, pady=2)
		self.settings_frame = LabelFrame(self, text='Settings')
		sets = Frame(self.settings_frame)
		if self.tiletype == TILETYPE_GROUP:
			g = LabelFrame(sets, text='Reuse MegaTiles')
			f = Frame(g)
			Checkbutton(f, text='Duplicates (Old)', variable=self.megatiles_reuse_duplicates_old, anchor=W).pack(side=LEFT)
			f.pack(side=TOP, fill=X)
			f = Frame(g)
			Checkbutton(f, text='Duplicates (New)', variable=self.megatiles_reuse_duplicates_new, anchor=W).pack(side=LEFT)
			f.pack(side=TOP, fill=X)
			f = Frame(g)
			Checkbutton(f, text='Null:', variable=self.megatiles_reuse_null, anchor=W).pack(side=LEFT)
			Entry(f, textvariable=self.megatiles_null_id, font=couriernew, width=5).pack(side=LEFT)
			Button(f, image=self.find, width=20, height=20, command=lambda *_: self.select_null(TILETYPE_MEGA)).pack(side=LEFT, padx=1)
			f.pack(side=TOP, fill=X)
			g.grid(column=0,row=0, padx=(0,3), sticky=W+E)
			sets.grid_columnconfigure(0, weight=1)
		g = LabelFrame(sets, text='Reuse MiniTiles')
		f = Frame(g)
		Checkbutton(f, text='Duplicates (Old)', variable=self.minitiles_reuse_duplicates_old, anchor=W).pack(side=LEFT)
		f.pack(side=TOP, fill=X)
		f = Frame(g)
		Checkbutton(f, text='Duplicates (New)', variable=self.minitiles_reuse_duplicates_new, anchor=W).pack(side=LEFT)
		f.pack(side=TOP, fill=X)
		f = Frame(g)
		Checkbutton(f, text='Null:', variable=self.minitiles_reuse_null, anchor=W).pack(side=LEFT)
		Entry(f, textvariable=self.minitiles_null_id, font=couriernew, width=5).pack(side=LEFT)
		Button(f, image=self.find, width=20, height=20, command=lambda *_: self.select_null(TILETYPE_MINI)).pack(side=LEFT, padx=1)
		f.pack(side=TOP, fill=X)
		g.grid(column=1,row=0, sticky=W+E)
		sets.grid_columnconfigure(1, weight=1)
		f = Frame(sets)
		Button(f, text='Reset to recommended settings', command=self.reset_options).pack(side=BOTTOM)
		g = Frame(f)
		Checkbutton(g, text='Replace palette selection', variable=self.replace_selections).pack(side=LEFT)
		Checkbutton(g, text='Auto-close', variable=self.auto_close).pack(side=LEFT, padx=(10,0))
		g.pack(side=BOTTOM)
		f.grid(column=0,row=1, columnspan=2, sticky=W+E)
		sets.pack(fill=X, expand=1, padx=3)
		self.settings_frame.pack(side=TOP, fill=X, padx=3, pady=(3,0))

		buts = Frame(self)
		self.import_button = Button(buts, text='Import', state=DISABLED, command=self.iimport)
		self.import_button.grid(column=0,row=0)
		Button(buts, text='Cancel', command=self.cancel).grid(column=2,row=0)
		buts.grid_columnconfigure(1, weight=1)
		buts.pack(side=BOTTOM, padx=3, pady=3, fill=X)

		self.update_states()

		return self.import_button
	def setup_complete(self):
		PYTILE_SETTINGS.windows['import'].graphics.load_window_size(('group','mega','mini')[self.tiletype], self)

	def load_settings(self):
		type_key = ''
		if self.tiletype == TILETYPE_GROUP:
			type_key = 'groups'
		elif self.tiletype == TILETYPE_MEGA:
			type_key = 'megatiles'
		elif self.tiletype == TILETYPE_MINI:
			type_key = 'minitiles'
		type_settings = PYTILE_SETTINGS['import'].graphics[type_key]
		self.megatiles_reuse_duplicates_old.set(type_settings.get('megatiles_reuse_duplicates_old',False))
		self.megatiles_reuse_duplicates_new.set(type_settings.get('megatiles_reuse_duplicates_new',False))
		self.megatiles_reuse_null.set(type_settings.get('megatiles_reuse_null',True))
		self.megatiles_null_id.set(type_settings.get('megatiles_null_id',0))
		self.minitiles_reuse_duplicates_old.set(type_settings.get('minitiles_reuse_duplicates_old',True))
		self.minitiles_reuse_duplicates_new.set(type_settings.get('minitiles_reuse_duplicates_new',True))
		self.minitiles_reuse_null.set(type_settings.get('minitiles_reuse_null',True))
		self.minitiles_null_id.set(type_settings.get('minitiles_null_id',0))
		self.replace_selections.set(type_settings.get('replace_selections',True))
		self.auto_close.set(type_settings.get('auto_close',True))

	def update_states(self, *_):
		self.import_button['state'] = NORMAL if self.graphics_list.size() else DISABLED
		sel = NORMAL if self.graphics_list.curselection() else DISABLED
		for b in self.sel_buttons:
			b['state'] = sel

	def iimport(self, *_):
		def can_expand():
			return askyesno(parent=self, title='Expand VX4', message="You have run out of minitiles, would you like to expand the VX4 file? If you don't know what this is you should google 'VX4 Expander Plugin' before saying Yes")
		options = {
			'minitiles_reuse_duplicates_old': self.minitiles_reuse_duplicates_old.get(),
			'minitiles_reuse_duplicates_new': self.minitiles_reuse_duplicates_new.get(),
			'minitiles_reuse_null_with_id': self.minitiles_null_id.get() if self.minitiles_reuse_null.get() else None,
			'minitiles_expand_allowed': can_expand,
			'megatiles_reuse_duplicates_old': self.megatiles_reuse_duplicates_old.get(),
			'megatiles_reuse_duplicates_new': self.megatiles_reuse_duplicates_new.get(),
			'megatiles_reuse_null_with_id': self.megatiles_null_id.get() if self.megatiles_reuse_null.get() else None,
		}
		ids = None
		if self.replace_selections.get():
			ids = sorted(self.ids)
		try:
			new_ids = self.tileset.import_graphics(self.tiletype, self.graphics_list.get(0,END), ids, options)
		except PyMSError, e:
			ErrorDialog(self, e)
		else:
			self.parent.imported_graphics(new_ids)
			if self.auto_close.get():
				self.ok()

	def select_paths(self, replace=False):
		paths = PYTILE_SETTINGS.lastpath.graphics.select_files('import', self, 'Choose Graphics', '.bmp', [('256 Color BMP','*.bmp'),('All Files','*')])
		if paths:
			if replace:
				self.graphics_list.delete(0, END)
			self.graphics_list.insert(END, *paths)
			self.graphics_list.xview_moveto(1.0)
			self.graphics_list.yview_moveto(1.0)
		self.update_states()

	def remove_paths(self, *_):
		for index in sorted(self.graphics_list.curselection(), reverse=True):
			self.graphics_list.delete(index)
		self.update_states()

	def shift_up(self):
		min_index = -1
		select = []
		for index in sorted(self.graphics_list.curselection()):
			move_to = index-1
			if move_to > min_index:
				select.append(move_to)
				item = self.graphics_list.get(index)
				self.graphics_list.delete(index)
				self.graphics_list.insert(move_to, item)
			else:
				min_index = index
				select.append(index)
		self.graphics_list.select_clear(0,END)
		for index in select:
			self.graphics_list.select_set(index)

	def shift_down(self):
		max_index = self.graphics_list.size()
		select = []
		for index in sorted(self.graphics_list.curselection(), reverse=True):
			move_to = index+1
			if move_to < max_index:
				select.append(move_to)
				item = self.graphics_list.get(index)
				self.graphics_list.delete(index)
				self.graphics_list.insert(move_to, item)
			else:
				max_index = index
				select.append(index)
		self.graphics_list.select_clear(0,END)
		for index in select:
			self.graphics_list.select_set(index)

	def select_null(self, tiletype):
		id = 0
		if tiletype == TILETYPE_MEGA:
			id = self.megatiles_null_id.get()
		elif tiletype == TILETYPE_MINI:
			id = self.minitiles_null_id.get()
		TilePalette(self, tiletype, id)
	def change(self, tiletype, id):
		if tiletype == TILETYPE_MEGA:
			self.megatiles_null_id.set(id)
		elif tiletype == TILETYPE_MINI:
			self.minitiles_null_id.set(id)

	def reset_options(self):
		if 'import' in PYTILE_SETTINGS:
			type_key = ''
			if self.tiletype == TILETYPE_GROUP:
				type_key = 'groups'
			elif self.tiletype == TILETYPE_MEGA:
				type_key = 'megatiles'
			elif self.tiletype == TILETYPE_MINI:
				type_key = 'minitiles'
			del PYTILE_SETTINGS['import'].graphics[type_key]
		self.load_settings()

	def dismiss(self, e=None):
		type_settings = {
			'minitiles_reuse_duplicates_old': not not self.minitiles_reuse_duplicates_old.get(),
			'minitiles_reuse_duplicates_new': not not self.minitiles_reuse_duplicates_new.get(),
			'minitiles_reuse_null': not not self.minitiles_reuse_null.get(),
			'minitiles_null_id': self.minitiles_null_id.get(),
			'replace_selections': not not self.replace_selections.get(),
			'auto_close': not not self.auto_close.get()
		}
		if self.tiletype != TILETYPE_MINI:
			type_settings['megatiles_reuse_duplicates_old'] = not not self.megatiles_reuse_duplicates_old.get()
			type_settings['megatiles_reuse_duplicates_new'] = not not self.megatiles_reuse_duplicates_new.get()
			type_settings['megatiles_reuse_null'] = not not self.megatiles_reuse_null.get()
			type_settings['megatiles_null_id'] = self.megatiles_null_id.get()
		type_key = ''
		if self.tiletype == TILETYPE_GROUP:
			type_key = 'groups'
		elif self.tiletype == TILETYPE_MEGA:
			type_key = 'megatiles'
		elif self.tiletype == TILETYPE_MINI:
			type_key = 'minitiles'
		PYTILE_SETTINGS['import'].graphics[type_key] = type_settings
		PYTILE_SETTINGS.windows['import'].graphics.save_window_size(('group','mega','mini')[self.tiletype], self)
		PyMSDialog.dismiss(self)

class MegaTileSettingsExporter(PyMSDialog):
	def __init__(self, parent, ids):
		self.ids = ids
		self.tileset = parent.tileset
		PyMSDialog.__init__(self, parent, 'Export MegaTile Settings', resizable=(False,False))

	def widgetize(self):
		self.height = IntVar()
		self.height.set(PYTILE_SETTINGS.export.megatiles.get('height',True))
		self.walkability = IntVar()
		self.walkability.set(PYTILE_SETTINGS.export.megatiles.get('walkability',True))
		self.block_sight = IntVar()
		self.block_sight.set(PYTILE_SETTINGS.export.megatiles.get('block_sight',True))
		self.ramp = IntVar()
		self.ramp.set(PYTILE_SETTINGS.export.megatiles.get('ramp',True))

		f = LabelFrame(self, text='Export')
		Checkbutton(f, text='Height', variable=self.height, anchor=W).grid(column=0,row=0, sticky=W)
		Checkbutton(f, text='Walkability', variable=self.walkability, anchor=W).grid(column=1,row=0, sticky=W)
		Checkbutton(f, text='Block Sight', variable=self.block_sight, anchor=W).grid(column=0,row=1, sticky=W)
		Checkbutton(f, text='Ramp', variable=self.ramp, anchor=W).grid(column=1,row=1, sticky=W)
		f.pack(side=TOP, padx=3, pady=(3,0))

		buts = Frame(self)
		self.export_button = Button(buts, text='Export', state=DISABLED, command=self.export)
		self.export_button.pack(side=LEFT)
		Button(buts, text='Cancel', command=self.cancel).pack(side=RIGHT, padx=(10,0))
		buts.pack(side=BOTTOM, padx=3, pady=3)

		self.height.trace('w', self.update_states)
		self.walkability.trace('w', self.update_states)
		self.block_sight.trace('w', self.update_states)
		self.ramp.trace('w', self.update_states)
		self.update_states()

		return self.export_button

	def update_states(self, *_):
		any_on = self.height.get() or self.walkability.get() or self.block_sight.get() or self.ramp.get()
		self.export_button['state'] = NORMAL if any_on else DISABLED

	def export(self):
		path = PYTILE_SETTINGS.lastpath.settings.select_file('export', self, 'Export MegaTile Settings', '.txt', [('Text File','*.txt'),('All Files','*')], save=True)
		if path:
			self.tileset.export_settings(TILETYPE_MEGA, path, sorted(self.ids))
			self.ok()

	def dismiss(self, e=None):
		PYTILE_SETTINGS.export.megatiles.height = not not self.height.get()
		PYTILE_SETTINGS.export.megatiles.walkability = not not self.walkability.get()
		PYTILE_SETTINGS.export.megatiles.block_sight = not not self.block_sight.get()
		PYTILE_SETTINGS.export.megatiles.ramp = not not self.ramp.get()
		PyMSDialog.dismiss(self)
class SettingsImporter(PyMSDialog):
	REPEATERS = (
		('Ignore',				'ignore',		Tilesets.setting_import_extras_ignore),
		('Repeat All Settings',	'repeat_all',	Tilesets.setting_import_extras_repeat_all),
		('Repeat Last Setting',	'repeat_last',	Tilesets.setting_import_extras_repeat_last)
	)
	def __init__(self, parent, tiletype, ids):
		self.tiletype = tiletype
		self.ids = ids
		self.tileset = parent.tileset
		typename = ''
		if self.tiletype == TILETYPE_GROUP:
			typename = 'MegaTile Group'
		elif self.tiletype == TILETYPE_MEGA:
			typename = 'MegaTile'
		PyMSDialog.__init__(self, parent, 'Import %s Settings' % typename, resizable=(True,False), set_min_size=(True,True))

	def widgetize(self):
		self.settings_path = StringVar()
		self.repeater = IntVar()
		repeater_n = 0
		repeater_setting = PYTILE_SETTINGS['import'].settings.get('repeater',SettingsImporter.REPEATERS[0][1])
		for n,(_,setting,_) in enumerate(SettingsImporter.REPEATERS):
			if setting == repeater_setting:
				repeater_n = n
				break
		self.repeater.set(repeater_n)
		self.auto_close = IntVar()
		self.auto_close.set(PYTILE_SETTINGS['import'].settings.get('auto_close', True))

		self.find = PhotoImage(file=os.path.join(BASE_DIR,'Images','find.gif'))
		f = Frame(self)
		Label(f, text='TXT:', anchor=W).pack(side=TOP, fill=X, expand=1)
		entryframe = Frame(f)
		self.settings_entry = Entry(entryframe, textvariable=self.settings_path, state=DISABLED)
		self.settings_entry.pack(side=LEFT, fill=X, expand=1)
		Button(entryframe, image=self.find, width=20, height=20, command=self.select_path).pack(side=LEFT, padx=(1,0))
		entryframe.pack(side=TOP, fill=X, expand=1)
		f.pack(side=TOP, fill=X, padx=3)

		sets = LabelFrame(self, text='Settings')
		f = Frame(sets)
		Label(f, text='Extra Tiles:', anchor=W).pack(side=TOP, fill=X)
		DropDown(f, self.repeater, [r[0] for r in SettingsImporter.REPEATERS], width=20).pack(side=TOP, fill=X)
		Checkbutton(f, text='Auto-close', variable=self.auto_close).pack(side=BOTTOM, padx=3, pady=(3,0))
		f.pack(side=TOP, fill=X, padx=3, pady=(0,3))
		sets.pack(side=TOP, fill=X, padx=3)

		buts = Frame(self)
		self.import_button = Button(buts, text='Import', state=DISABLED, command=self.iimport)
		self.import_button.pack(side=LEFT)
		Button(buts, text='Cancel', command=self.cancel).pack(side=RIGHT, padx=(10,0))
		buts.pack(side=BOTTOM, fill=X, padx=3, pady=3)

		self.settings_path.trace('w', self.update_states)

		return self.import_button

	def select_path(self):
		typename = ''
		if self.tiletype == TILETYPE_GROUP:
			typename = 'MegaTile Group'
		elif self.tiletype == TILETYPE_MEGA:
			typename = 'MegaTile'
		path = PYTILE_SETTINGS.lastpath.settings.select_file('import', self, 'Import %s Settings' % typename, '.txt', [('Text File','*.txt'),('All Files','*')])
		if path:
			self.settings_path.set(path)
			self.settings_entry.xview(END)
			self.update_states()

	def update_states(self, *_):
		self.import_button['state'] = NORMAL if self.settings_path.get() else DISABLED

	def iimport(self):
		try:
			self.tileset.import_settings(self.tiletype, self.settings_path.get(), sorted(self.ids), {'repeater': SettingsImporter.REPEATERS[self.repeater.get()][2]})
		except PyMSError, e:
			ErrorDialog(self, e)
		else:
			self.parent.mark_edited()
			if self.auto_close.get():
				self.ok()

	def dismiss(self, e=None):
		PYTILE_SETTINGS['import'].settings.repeater = SettingsImporter.REPEATERS[self.repeater.get()][1]
		PYTILE_SETTINGS['import'].settings.auto_close = not not self.auto_close.get()
		PyMSDialog.dismiss(self)

class TilePaletteView(Frame):
	# sub_select currently only supported by TILETYPE_GROUP when multiselect=False
	def __init__(self, parent, tiletype=TILETYPE_GROUP, select=None, delegate=None, multiselect=True, sub_select=False, pytile=None):
		Frame.__init__(self, parent)
		self.parent = pytile
		self.tiletype = tiletype
		self.selected = []
		self.last_selection = None # (index, on_or_off)
		self.sub_selection = 0
		self.scale = 1
		if select != None:
			if isinstance(select, list):
				self.selected.extend(sorted(select))
			else:
				self.selected.append(select)
		self.delegate = delegate or parent
		self.multiselect = multiselect
		if not multiselect:
			if not self.selected:
				self.selected.append(0)
			elif len(self.selected) > 1:
				self.selected = self.selected[:1]
		self.sub_select = not self.multiselect and sub_select

		self.visible_range = None
		self.get_tile = self.delegate.tile_palette_get_tile()

		tile_size = self.get_tile_size()
		self.originalWidth = 2 + tile_size[0] * 16
		self.canvas = Tkinter.Canvas(self, width=self.originalWidth, height=2 + tile_size[1] * 8, background='#000000', highlightthickness=0)
		self.canvas.images = {}
		self.canvas.pack(side=LEFT, fill=BOTH, expand=1, padx=(3,0))
		scrollbar = Scrollbar(self, command=self.canvas.yview)
		scrollbar.pack(side=LEFT, fill=Y)

		self.resizeForceUpdate = False
		def canvas_resized(e):
			self.update_size()

		self.canvas.bind('<Configure>', canvas_resized)
		binding_widget = self.delegate.tile_palette_binding_widget()
		binding_widget.bind('<MouseWheel>', lambda e: self.canvas.yview('scroll', -(e.delta / abs(e.delta)) if e.delta else 0,'units'))
		if not hasattr(self.delegate, 'tile_palette_bind_updown') or self.delegate.tile_palette_bind_updown():
			binding_widget.bind('<Down>', lambda e: self.canvas.yview('scroll', 1,'units'))
			binding_widget.bind('<Up>', lambda e: self.canvas.yview('scroll', -1,'units'))
		binding_widget.bind('<Next>', lambda e: self.canvas.yview('scroll', 1,'page'))
		binding_widget.bind('<Prior>', lambda e: self.canvas.yview('scroll', -1,'page'))
		def update_scrollbar(l,h,bar):
			scrollbar.set(l,h)
			self.draw_tiles()
		self.canvas.config(yscrollcommand=lambda l,h,s=scrollbar: update_scrollbar(l,h,s))

	def setScale(self, scale):
		self.resizeForceUpdate = True
		self.scale = scale
		self.canvas.config(width=self.originalWidth * self.scale)

	def get_tile_size(self, tiletype=None, group=False):
		tiletype = self.tiletype if tiletype == None else tiletype
		if tiletype == TILETYPE_GROUP:
			return [32.0*self.scale * (16 if group else 1),32.0*self.scale + 1]
		elif tiletype == TILETYPE_MEGA:
			return [32.0*self.scale + (0 if self.tiletype == TILETYPE_GROUP else 1*self.scale), 32.0*self.scale + (0 if self.tiletype == TILETYPE_GROUP else 1*self.scale)]
		elif tiletype == TILETYPE_MINI:
			return [25.0*self.scale,25.0*self.scale]
	def get_tile_count(self):
		tileset = self.delegate.tile_palette_get_tileset()
		if not tileset:
			return 0
		if self.tiletype == TILETYPE_GROUP:
			return len(tileset.cv5.groups) * 16
		elif self.tiletype == TILETYPE_MEGA:
			return len(tileset.vx4.graphics)
		elif self.tiletype == TILETYPE_MINI:
			return len(tileset.vr4.images)
	def get_total_size(self):
		tile_size = self.get_tile_size()
		tile_count = self.get_tile_count()
		width = self.canvas.winfo_width()
		columns = floor(width / tile_size[0])
		total_size = [0,0]
		if columns:
			total_size = [width,int(ceil(tile_count / columns)) * tile_size[1] + 1]
		return total_size

	def update_size(self, force_draw=False):
		total_size = self.get_total_size()
		self.canvas.config(scrollregion=(0,0,total_size[0],total_size[1]))
		self.draw_tiles(force=force_draw or self.resizeForceUpdate)
		self.resizeForceUpdate = False

	def draw_selections(self):
		self.canvas.delete('selection')
		self.canvas.delete('sub_selection')
		tile_size = self.get_tile_size(group=True)
		tile_count = self.get_tile_count()
		columns = int(floor(self.canvas.winfo_width() / tile_size[0]))
		if columns:
			for id in self.selected:
				x = (id % columns) * tile_size[0]
				y = (id / columns) * tile_size[1]
				self.canvas.create_rectangle(x, y, x+tile_size[0]+(1 if self.sub_select or self.tiletype == TILETYPE_GROUP else 0), y+tile_size[1], outline='#AAAAAA' if self.sub_select else '#FFFFFF', tags='selection')
				if self.sub_select and self.multiselect == False:
					mega_size = self.get_tile_size(TILETYPE_MEGA, group=True)
					x += mega_size[0] * self.sub_selection
					self.canvas.create_rectangle(x, y, x+mega_size[0]+1, y+mega_size[1]+1, outline='#FFFFFF', tags='sub_selection')

	class MegatileInfo():
		def __init__(self, id, x, y, megatile_id, tile_tag, bind_tag):
			self.id = id
			self.x = x
			self.y = y
			self.megatile_id = megatile_id
			self.tile_tag = tile_tag
			self.bind_tag = bind_tag

	def get_megatile_id(self, id):
		return self.parent.tileset.cv5.groups[id / 16][13][id % 16]

	def mouse_to_mini(self, e, megatile_info):
		totalHeight = float((self.canvas.cget('scrollregion') or '0').split(' ')[-1])
		scroll = floor((self.canvas.yview()[0] * totalHeight))

		def clamp(value, min, max):
			if (value < min):
				return min
			if (value > max):
				return max
			return value

		localX = ((e.x) - megatile_info.x)
		localY = ((e.y + scroll) - megatile_info.y)

		x = clamp(floor(localX / (8 * self.scale)), 0, 3)
		y = clamp(floor(localY / (8 * self.scale)), 0, 3)

		return int(y * 4 + x)

	def draw_minitile_flag(self, megatile_info, minitile_n, color='#FFFFFF'):
		minitile_x = megatile_info.x + 8 * self.scale * (minitile_n % 4)
		minitile_y = megatile_info.y + 8 * self.scale * (minitile_n / 4)
		tile_tag = megatile_info.tile_tag
		bind_tag = megatile_info.bind_tag

		style = self.parent.style.get()
		if style == STYLE_BOXES or style == STYLE_BOXES_AND_DOTS:
			self.canvas.create_rectangle(minitile_x + 1 * self.scale, minitile_y + 1 * self.scale,
										 minitile_x + 7 * self.scale - 1, minitile_y + 7 * self.scale - 1,
										 outline=color, tags=(tile_tag, bind_tag))

		if style == STYLE_DOTS or style == STYLE_BOXES_AND_DOTS:
			self.canvas.create_rectangle(minitile_x + 3 * self.scale, minitile_y + 3 * self.scale,
										 minitile_x + 5 * self.scale, minitile_y + 5 * self.scale,
										 fill=color, outline="", tags=(tile_tag, bind_tag))

	def get_buildable_flag(self, megatile_info):
		return self.parent.tileset.cv5.groups[megatile_info.id/16][1]

	def draw_buildable(self, megatile_info):
		tile = self.get_buildable_flag(megatile_info)

		if tile == 0:
			return

		# red for unbuildable, purple for creep
		color = "#FF0000" if tile == 8 else "#800080"

		x = megatile_info.x
		y = megatile_info.y
		tile_tag = megatile_info.tile_tag
		bind_tag = megatile_info.bind_tag

		self.canvas.create_rectangle(x, y, x+32*self.scale, y+32*self.scale, outline="", fill=color, stipple="gray12", tags=(tile_tag, bind_tag));

	def draw_flags(self, megatile_info):
		if not hasattr(self, "parent"):
			return

		if megatile_info.megatile_id == 0 or not self.parent.tileset:
			return

		if self.parent.show_buildable.get():
			self.draw_buildable(megatile_info)

		if self.parent.show_minitiles.get():
			mode = self.parent.mega_editor.edit_mode.get()
			if mode == MEGA_EDIT_MODE_HEIGHT:
				self.draw_height(megatile_info)
			elif mode == MEGA_EDIT_MODE_WALKABILITY:
				self.draw_walkability(megatile_info)
			elif mode == MEGA_EDIT_MODE_VIEW_BLOCKING:
				self.draw_blocking(megatile_info)
			elif mode == MEGA_EDIT_MODE_RAMP:
				self.draw_ramp(megatile_info)

	def draw_height(self, megatile_info):
		for n in xrange(16):
			flags = self.parent.mega_editor.delegate.tileset.vf4.flags[megatile_info.megatile_id][n]
			color = '#FF0000'
			if flags & HEIGHT_MID:
				color = '#FF7F00'
			elif flags & HEIGHT_HIGH:
				color = '#FFFF00'
			self.draw_minitile_flag(megatile_info, n, color)

	def draw_walkability(self, megatile_info):
		for n in xrange(16):
			flags = self.parent.mega_editor.delegate.tileset.vf4.flags[megatile_info.megatile_id][n]
			self.draw_minitile_flag(megatile_info, n, '#00FF00' if flags & 1 else '#FF0000')

	def draw_blocking(self, megatile_info):
		for n in xrange(16):
			flags = self.parent.mega_editor.delegate.tileset.vf4.flags[megatile_info.megatile_id][n]
			self.draw_minitile_flag(megatile_info, n, '#FF0000' if flags & 8 else '#00FF00')

	def draw_ramp(self, megatile_info):
		for n in xrange(16):
			flags = self.parent.mega_editor.delegate.tileset.vf4.flags[megatile_info.megatile_id][n]
			self.draw_minitile_flag(megatile_info, n, '#00FF00' if flags & 16 else '#FF0000')

	def draw_tiles(self, force=False):
		tileset = self.delegate.tile_palette_get_tileset()
		if force or not tileset:
			self.visible_range = None
			self.canvas.delete(ALL)
			self.canvas.images.clear()
		if not tileset:
			return
		viewport_size = [self.originalWidth * self.scale, self.winfo_height()]
		tile_size = self.get_tile_size()
		tile_count = self.get_tile_count()
		total_height = float((self.canvas.cget('scrollregion') or '0').split(' ')[-1])
		topy = int(self.canvas.yview()[0] * total_height)
		start_row = int(floor(topy / tile_size[1]))
		start_y = start_row * int(tile_size[1])
		tiles_size = [int(floor(viewport_size[0] / tile_size[0])),int(ceil((viewport_size[1] + topy-start_y) / tile_size[1]))]
		first = start_row * tiles_size[0]
		last = min(tile_count,first + tiles_size[0] * tiles_size[1]) - 1
		visible_range = [first,last]

		if visible_range != self.visible_range:
			update_ranges = [visible_range]
			overlaps = self.visible_range \
				and ((self.visible_range[0] <= visible_range[0] <= self.visible_range[1] or self.visible_range[0] <= visible_range[1] <= self.visible_range[1]) \
				or (visible_range[0] <= self.visible_range[0] <= visible_range[1] or visible_range[0] <= self.visible_range[1] <= visible_range[1]))
			if overlaps:
				update_ranges = [[min(self.visible_range[0],visible_range[0]),max(self.visible_range[1],visible_range[1])]]
			elif self.visible_range:
				update_ranges.append(self.visible_range)

			for update_range in update_ranges:
				for id in range(update_range[0],update_range[1]+1):

					if (id < visible_range[0] or id > visible_range[1]) and id >= self.visible_range[0] and id <= self.visible_range[1]:
						del self.canvas.images[id]
						self.canvas.delete('tile%s' % id)
					else:
						n = id - visible_range[0]
						x = 1 + (n % tiles_size[0]) * tile_size[0]
						y = 1 + start_y + floor(n / tiles_size[0]) * tile_size[1]
						if self.visible_range and id >= self.visible_range[0] and id <= self.visible_range[1]:
							self.canvas.coords('tile%s' % id, x, y)
						else:
							if self.tiletype == TILETYPE_GROUP:
								group = int(id / 16.0)
								megatile = tileset.cv5.groups[group][13][id % 16]
								self.canvas.images[id] = self.get_tile(megatile, cache=(not force))
							elif self.tiletype == TILETYPE_MEGA:
								self.canvas.images[id] = self.get_tile(id, cache=(not force))
							elif self.tiletype == TILETYPE_MINI:
								self.canvas.images[id] = self.get_tile((id, 0), cache=(not force))

							self.canvas.images[id] = self.canvas.images[id]._PhotoImage__photo.zoom(self.scale)
							flags = self.parent != None and self.multiselect == False
							tile_tag = 'tile%s' % id
							bind_tag = 'tile%s%s' % (id, "f" if flags else "nf")
							self.canvas.delete(tile_tag)
							self.canvas.create_image(x, y, image=self.canvas.images[id], tags=(tile_tag, bind_tag), anchor=NW)

							def select(id, modifier=None):
								sub_select = None
								if self.tiletype == TILETYPE_GROUP:
									if self.sub_select:
										sub_select = id % 16
									id /= 16
								self.select(id, sub_select, modifier)

							if self.parent != None:
								megatile_info = TilePaletteView.MegatileInfo(id, x, y, self.get_megatile_id(id), tile_tag, bind_tag)
								self.draw_flags(megatile_info)

							if flags:
								def make_last_click(megatile, minitile):
									return str(megatile) + "," + str(minitile)

								def click(e, megatile_info, mouseButton, fill=False, ctrl=False):
									select(megatile_info.id, "cntrl" if ctrl else None)
									if self.parent.show_minitiles.get() and self.parent.edit_minitiles.get() and megatile_info.megatile_id != 0:
										mini = self.mouse_to_mini(e, megatile_info)
										if (fill):
											self.last_click = make_last_click(megatile_info.megatile_id, mini)
											self.parent.mega_editor.fill_minitiles(mini, mouseButton)
											self.draw_flags(megatile_info)
											return

										if mini != None:
											self.last_click = make_last_click(megatile_info.megatile_id, mini)
											self.parent.mega_editor.click_minitile(mini, mouseButton, True)
											self.draw_flags(megatile_info)

								def move(e, megatile_info, mouseButton):
									if self.parent.show_minitiles.get() and self.parent.edit_minitiles.get() and megatile_info.megatile_id != 0:
										mini = self.mouse_to_mini(e, megatile_info)
										if mini != None and make_last_click(megatile_info.megatile_id, mini) != self.last_click:
											self.last_click = make_last_click(megatile_info.megatile_id, mini)
											self.parent.mega_editor.click_minitile(mini, mouseButton, True)
											self.draw_flags(megatile_info)

								def release(_):
									self.last_click = None
									self.last_click_mega = None
									self.toggle_on = None

								def click_alt(e, megatile_info):
									select(megatile_info.id)
									self.last_click_mega = megatile_info.id
									self.parent.megatile_null_current()

								self.canvas.tag_bind(bind_tag, '<Button-1>', lambda e, megatile_info=megatile_info: click(e, megatile_info, 0))
								self.canvas.tag_bind(bind_tag, '<Button-2>', lambda e, megatile_info=megatile_info: click(e, megatile_info, 1))
								self.canvas.tag_bind(bind_tag, '<Button-3>', lambda e, megatile_info=megatile_info: click(e, megatile_info, 2))
								self.canvas.tag_bind(bind_tag, '<Control-Button-1>', lambda e, megatile_info=megatile_info: click(e, megatile_info, 0, True, True))
								self.canvas.tag_bind(bind_tag, '<Control-Button-2>', lambda e, megatile_info=megatile_info: click(e, megatile_info, 1, True))
								self.canvas.tag_bind(bind_tag, '<Control-Button-3>', lambda e, megatile_info=megatile_info: click(e, megatile_info, 2, True))
								self.canvas.tag_bind(bind_tag, '<B1-Motion>', lambda e, megatile_info=megatile_info: move(e, megatile_info, 0))
								self.canvas.tag_bind(bind_tag, '<B2-Motion>', lambda e, megatile_info=megatile_info: move(e, megatile_info, 1))
								self.canvas.tag_bind(bind_tag, '<B3-Motion>', lambda e, megatile_info=megatile_info: move(e, megatile_info, 2))
								self.canvas.tag_bind(bind_tag, '<ButtonRelease-1>', release)
								self.canvas.tag_bind(bind_tag, '<ButtonRelease-2>', release)
								self.canvas.tag_bind(bind_tag, '<ButtonRelease-3>', release)

								self.canvas.tag_bind(bind_tag, '<Alt-Button-1>',
													 lambda e, megatile_info=megatile_info: click_alt(e, megatile_info))

							else:
								self.canvas.tag_bind(bind_tag, '<Button-1>', lambda e, id=id: select(id))
								self.canvas.tag_bind(bind_tag, '<Button-2>', lambda e, id=id: select(id))
								self.canvas.tag_bind(bind_tag, '<Button-3>', lambda e, id=id: select(id))
								self.canvas.tag_bind(bind_tag, '<Control-Button-1>',  lambda e, id=id: select(id, 'cntrl'))

							self.canvas.tag_bind(bind_tag, '<Shift-Button-1>', lambda e, id=id: select(id, 'shift'))
							if hasattr(self.delegate, 'tile_palette_double_clicked'):
								self.canvas.tag_bind(bind_tag, '<Double-Button-1>', lambda e,id=id / (16 if self.tiletype == TILETYPE_GROUP else 1): self.delegate.tile_palette_double_clicked(id))

			self.visible_range = visible_range
			self.draw_selections()

	def select(self, select, sub_select=None, modifier=None, scroll_to=False):
		if self.multiselect:
			if modifier == 'shift':
				if self.last_selection != None:
					last_select,enable = self.last_selection
					start = min(last_select,select)
					end = max(last_select,select)
					for index in xrange(start,end+1):
						if enable and not index in self.selected:
							self.selected.append(index)
						elif not enable and index in self.selected:
							self.selected.remove(index)
					if enable:
						self.selected.sort()
					self.last_selection = (select, enable)
					select = None
				else:
					modifier = 'cntrl'
			if modifier == 'cntrl':
				if select in self.selected:
					self.selected.remove(select)
					self.last_selection = (select, False)
				else:
					self.selected.append(select)
					self.selected.sort()
					self.last_selection = (select, True)
			elif select != None:
				if isinstance(select, list):
					select = sorted(select)
				else:
					select = [select]
				self.selected = select
				if self.selected:
					self.last_selection = (self.selected[-1], True)
				else:
					self.last_selection = None
		else:
			if isinstance(select, list):
				select = select[0] if select else 0
			self.selected = [select]
			if sub_select != None:
				self.sub_selection = sub_select
		self.draw_selections()
		if scroll_to:
			self.scroll_to_selection()
		if hasattr(self.delegate, 'tile_palette_selection_changed'):
			self.delegate.tile_palette_selection_changed()

	def scroll_to_selection(self):
		if not len(self.selected):
			return
		tile_size = self.get_tile_size(group=True)
		tile_count = self.get_tile_count()
		viewport_size = [self.canvas.winfo_width(),self.canvas.winfo_height()]
		columns = int(floor(viewport_size[0] / tile_size[0]))
		if not columns:
			return
		total_size = self.get_total_size()
		max_y = total_size[1] - viewport_size[1]
		id = self.selected[0]
		y = max(0,min(max_y,(id / columns + 0.5) * tile_size[1] - viewport_size[1]/2.0))
		self.canvas.yview_moveto(y / total_size[1])

class TilePalette(PyMSDialog):
	def __init__(self, parent, tiletype=TILETYPE_GROUP, select=None, delegate=None, editing=False):
		PAL[0] += 1
		self.tiletype = tiletype
		self.start_selected = []
		if select != None:
			if isinstance(select, list):
				self.start_selected.extend(sorted(select))
			else:
				self.start_selected.append(select)
		self.delegate = delegate or parent
		self.tileset = parent.tileset
		self.get_tile = parent.get_tile
		self.editing = editing
		self.edited = False
		PyMSDialog.__init__(self, parent, self.get_title(), resizable=(False, True), set_min_size=(True,True))

	def widgetize(self):
		typename = ''
		smallertype = ''
		if self.tiletype == TILETYPE_GROUP:
			typename = 'MegaTile Groups'
			smallertype = 'MegaTiles'
		elif self.tiletype == TILETYPE_MEGA:
			typename = 'MegaTiles'
			smallertype = 'MiniTiles'
		elif self.tiletype == TILETYPE_MINI:
			typename = 'MiniTiles'
		self.buttons = None
		if self.editing:
			buttons = [
				('add', self.add, 'Add (Insert)', NORMAL, 'Insert'),
			]

			if self.tiletype == TILETYPE_GROUP:
				buttons.extend([
					('arrow', self.insert, 'Insert (Ctrl+Insert)', DISABLED, 'Ctrl+Insert'),
				])

			tiletype = "Mega" if self.tiletype == TILETYPE_MEGA else "Mini"

			buttons.extend([('remove', self.remove, 'Remove (Delete)', NORMAL, 'Delete'),])
			if self.tiletype == TILETYPE_MEGA or self.tiletype == TILETYPE_MINI:
				buttons.extend([
					('asc3topyai', self.clean, tiletype+'tile Cleanup (Ctrl+Delete)', NORMAL, 'Ctrl+Delete')
				])

			if self.tiletype == TILETYPE_GROUP:
				buttons.extend([
					10,
					('up', self.up, 'Move Up (Shift+W)', DISABLED, 'Shift+W'),
					('down', self.down, 'Move Down (Shift+S)', DISABLED, 'Shift+S'),
					('redo', self.swap, 'Swap groups (Ctrl+W)', DISABLED, 'Ctrl+S')
				])

			buttons.extend([
					10,
					('end', lambda *_: self.palette.draw_tiles(True), 'Force Redraw Palette (Ctrl+A)', NORMAL, 'Ctrl+A')
			])

			if self.tiletype != TILETYPE_MINI:
				buttons.extend([
					10,
					('colors', self.select_smaller, 'Select %s (Ctrl+M)' % smallertype, NORMAL, 'Ctrl+M'),
				])
			if self.tiletype != TILETYPE_GROUP:
				buttons.extend([
					10,
					('edit', self.edit, 'Edit %s (Enter)' % typename, NORMAL, 'Return')
				])
			buttons.extend([
				10,
				('importc', self.import_graphics, 'Import %s Graphics (Ctrl+I)' % typename, NORMAL, 'Ctrl+I'),
				('exportc', self.export_graphics, 'Export %s Graphics (Ctrl+E)' % typename, NORMAL, 'Ctrl+E'),
			])
			if self.tiletype != TILETYPE_MINI:
				buttons.extend([
					10,
					('import', self.import_settings, 'Import %s Settings (Ctrl+Shift+I)' % typename, NORMAL, 'Ctrl+Shift+I'),
					('export', self.export_settings, 'Export %s Settings (Ctrl+Shift+E)' % typename, NORMAL, 'Ctrl+Shift+E'),
				])
			self.buttons = {}
			toolbar = Frame(self)
			for btn in buttons:
				if isinstance(btn, tuple):
					image = PhotoImage(file=os.path.join(BASE_DIR,'Images','%s.gif' % btn[0]))
					button = Button(toolbar, image=image, width=20, height=20, command=btn[1], state=btn[3])
					button.image = image
					button.tooltip = Tooltip(button, btn[2])
					button.pack(side=LEFT)
					self.buttons[btn[0]] = button
					a = btn[4]
					if a:
						if not a.startswith('F'):
							if a.find("Shift") != -1:
								self.bind('<%s>' % (a[:].replace('Ctrl','Control').replace('+','-')), btn[1])
							else:
								self.bind('<%s%s>' % (a[:-1].replace('Ctrl','Control').replace('+','-'), a[-1].lower()), btn[1])
						else:
							self.bind('<%s>' % a, btn[1])
				else:
					Frame(toolbar, width=btn).pack(side=LEFT)
			toolbar.pack(fill=X)

		self.palette = TilePaletteView(self, self.tiletype, self.start_selected)
		self.palette.pack(side=TOP, fill=BOTH, expand=1)

		self.status = StringVar()
		self.update_status()
		self.update_state()

		statusbar = Frame(self)
		Label(statusbar, textvariable=self.status, bd=1, relief=SUNKEN, anchor=W).pack(side=LEFT, fill=X, expand=1, padx=1)
		statusbar.pack(side=BOTTOM, fill=X)

	def tile_palette_get_tileset(self):
		return self.tileset

	def tile_palette_get_tile(self):
		return self.get_tile

	def tile_palette_binding_widget(self):
		return self

	def tile_palette_double_clicked(self, id):
		if not hasattr(self.delegate, 'change'):
			return
		self.delegate.change(self.tiletype, id)
		self.ok()

	def tile_palette_selection_changed(self):
		self.update_status()
		self.update_state()
		self.palette.draw_selections()

	def setup_complete(self):
		PYTILE_SETTINGS.windows.palette.load_window_size(('group','mega','mini')[self.tiletype], self)

		if len(self.start_selected):
			self.after(100, self.palette.scroll_to_selection)

	def select_smaller(self, *_):
		ids = []
		for id in self.palette.selected:
			if self.tiletype == TILETYPE_GROUP:
				for sid in self.tileset.cv5.groups[id][13]:
					if sid and not sid in ids:
						ids.append(sid)
			elif self.tiletype == TILETYPE_MEGA:
				for sid,_ in self.tileset.vx4.graphics[id]:
					if not sid in ids:
						ids.append(sid)
		TilePalette(self.parent, TILETYPE_MEGA if self.tiletype == TILETYPE_GROUP else TILETYPE_MINI, ids, editing=True)

	def mark_edited(self):
		self.edited = True

	def get_title(self):
		count = 0
		max_count = 0
		if self.tiletype == TILETYPE_GROUP:
			count = len(self.tileset.cv5.groups)
			max_count = self.tileset.groups_max()
		elif self.tiletype == TILETYPE_MEGA:
			count = len(self.tileset.vx4.graphics)
			max_count = self.tileset.megatiles_max()
		elif self.tiletype == TILETYPE_MINI:
			count = len(self.tileset.vr4.images)
			max_count = self.tileset.minitiles_max()
		return '%s Palette [%d/%d]' % (['Group','MegaTile','MiniTile Image'][self.tiletype], count,max_count)
	def update_title(self):
		self.title(self.get_title())

	def update_state(self):
		if self.buttons == None:
			return
		at_max = False
		if self.tiletype == TILETYPE_GROUP:
			at_max = (self.tileset.groups_remaining() == 0)
		elif self.tiletype == TILETYPE_MEGA:
			at_max = (self.tileset.megatiles_remaining() == 0)
		elif self.tiletype == TILETYPE_MINI:
			at_max = (self.tileset.minitiles_remaining() == 0 and self.tileset.vx4.expanded)
		self.buttons['add']['state'] == DISABLED if at_max else NORMAL
		export_state = DISABLED if not self.palette.selected else NORMAL
		self.buttons['exportc']['state'] = export_state
		if 'export' in self.buttons:
			self.buttons['export']['state'] = export_state

	def update_status(self):
		status = 'Selected: '
		if len(self.palette.selected):
			for id in self.palette.selected:
				status += '%s ' % id
		else:
			status += 'None'

		if self.tiletype == TILETYPE_GROUP:
			if len(self.palette.selected) == 1:
				self.buttons['arrow']['state'] = NORMAL
			else:
				self.buttons['arrow']['state'] = DISABLED

			if len(self.palette.selected) > 0:
				self.buttons['up']['state'] = NORMAL
				self.buttons['down']['state'] = NORMAL
			else:
				self.buttons['up']['state'] = DISABLED
				self.buttons['down']['state'] = DISABLED

			if len(self.palette.selected) == 2:
				self.buttons['redo']['state'] = NORMAL
			else:
				self.buttons['redo']['state'] = DISABLED

		self.status.set(status)

	def add(self, *_):
		select = 0
		if self.tiletype == TILETYPE_GROUP:
			self.tileset.cv5.groups.append([0] * 13 + [[0] * 16])
			select = len(self.tileset.cv5.groups)-1
		elif self.tiletype == TILETYPE_MEGA:
			self.tileset.vf4.flags.append([0]*32)
			self.tileset.vx4.add_tile(((0,0),)*16)
			select = len(self.tileset.vx4.graphics)-1
		else:
			if self.tileset.minitiles_remaining() == 0:
				if not askyesno(parent=self, title='Expand VX4', message="You have run out of minitiles, would you like to expand the VX4 file? If you don't know what this is you should google 'VX4 Expander Plugin' before saying Yes"):
					return
				self.tileset.vx4.expanded = True
			for _ in range(1 if self.tileset.vx4.expanded else self.tileset.minitiles_remaining()):
				self.tileset.vr4.add_image(((0,)*8,)*8)
			select = len(self.tileset.vr4.images)-1
		self.update_title()
		self.update_state()
		self.palette.update_size()
		self.palette.select(select, scroll_to=True)
		self.parent.update_ranges()
		self.mark_edited()

	def refresh(self):
		self.update_title()
		self.update_state()
		self.palette.update_size(True)
		self.parent.update_ranges()
		self.mark_edited()

	def remove(self, *_):
		if self.buttons['remove']['state'] != NORMAL:
			return

		if self.tiletype == TILETYPE_GROUP:
			current_ids = self.palette.selected
			self.remove_groups(current_ids)
		else:
			current_ids = self.palette.selected
			self.remove_tiles(current_ids)

		self.refresh()

	def insert(self, *_):
		if self.buttons['arrow']['state'] != NORMAL or self.tiletype != TILETYPE_GROUP:
			return
		selected = self.palette.selected[0]
		self.insert_group(selected)
		self.palette.select(selected+1, scroll_to=True)
		self.refresh()

	def insert_group(self, id):
		groups = self.tileset.cv5.groups
		groups_new = []

		for i in range(id+1):
			groups_new.append(groups[i])

		groups_new.append([0] * 13 + [[0] * 16])

		for i in range(id+1, len(groups)):
			groups_new.append(groups[i])


		for i, doodad in enumerate(self.tileset.dddata.doodads):
			for j, did in enumerate(doodad):
				if did > id+1:
					self.tileset.dddata.doodads[i][j] += 1

		self.tileset.cv5.groups = groups_new

	def up(self, *_):
		if self.buttons['up']['state'] != NORMAL or self.tiletype != TILETYPE_GROUP:
			return
		selected = sorted(self.palette.selected)

		for group in selected:
			self.swap_groups(group, group - 1)

		for i in range(len(self.palette.selected)):
			self.palette.selected[i] -= 1

		self.refresh()

	def down(self, *_):
		if self.buttons['down']['state'] != NORMAL or self.tiletype != TILETYPE_GROUP:
			return
		selected = sorted(self.palette.selected, reverse=True)

		for group in selected:
			self.swap_groups(group, group + 1)

		for i in range(len(self.palette.selected)):
			self.palette.selected[i] += 1

		self.refresh()

	def swap(self, *_):
		if self.buttons['redo']['state'] != NORMAL or self.tiletype != TILETYPE_GROUP:
			return
		selected = self.palette.selected
		if len(selected) != 2:
			return

		self.swap_groups(selected[0], selected[1])
		self.refresh()

	def remove_tiles(self, ids):
		if len(ids) == 0:
			return
		if self.tiletype == TILETYPE_MEGA:
			graphics = []
			lookup = {}
			flags = []

			i = 0
			for id, graphic in enumerate(self.tileset.vx4.graphics):
				if id not in ids:
					graphics.append(graphic)
					tile_hash = hash(graphic)
					lookup[tile_hash] = i
					i += 1

			for id, flag in enumerate(self.tileset.vf4.flags):
				if id not in ids:
					flags.append(flag)

			self.tileset.vx4.graphics = graphics
			self.tileset.vx4.lookup = lookup
			self.tileset.vf4.flags = flags

			self.reevaluate_references(ids)
		elif self.tiletype == TILETYPE_MINI:
			images = []
			lookup = {}

			i = 0
			for id, image in enumerate(self.tileset.vr4.images):
				if id not in ids:
					images.append(image)
					tile_hash = hash(image)
					lookup[tile_hash] = i
					i += 1

			self.tileset.vr4.images = images
			self.tileset.vr4.lookup = lookup

			self.reevaluate_references(ids)

	def binarySearchCount(self, arr, val):
		n = len(arr)
		left = 0
		right = n

		mid = 0
		while (left < right):

			mid = (right + left) // 2

			# Check if key is present in array
			if (arr[mid] == val):

				# If duplicates are
				# present it returns
				# the position of last element
				while (mid + 1 < n and arr[mid + 1] == val):
					mid += 1
				break


			# If key is smaller,
			# ignore right half
			elif (arr[mid] > val):
				right = mid

			# If key is greater,
			# ignore left half
			else:
				left = mid + 1

		# If key is not found in
		# array then it will be
		# before mid
		while (mid > -1 and arr[mid] > val):
			mid -= 1

		# Return mid + 1 because
		# of 0-based indexing
		# of array
		return mid + 1

	def get_decrease_value(self, ids, id):
		return self.binarySearchCount(ids, id)

		decrease = 0
		for i in ids:
			if id > i:
				decrease += 1

		return decrease

	def reevaluate_references(self, ids):
		if len(ids) == 0:
			return
		#ids = sorted(ids) # binary search needs a sorted array
		if self.tiletype == TILETYPE_MEGA:
			for group in self.tileset.cv5.groups:
				for i, id in enumerate(group[13]):
					if id in ids:
						group[13][i] = 0
					else:
						group[13][i] -= self.get_decrease_value(ids, id)
		elif self.tiletype == TILETYPE_MINI:
			megatiles_new = []
			for megatile in self.tileset.vx4.graphics:
				megatile_new = []
				for i, values in enumerate(megatile):
					values_new = []
					if values[0] in ids:
						values_new.append(0)
					else:
						values_new.append(values[0] - self.get_decrease_value(ids, values[0]))
					values_new.append(values[1])
					megatile_new.append(tuple(values_new))
				megatiles_new.append(tuple(megatile_new))
			self.tileset.vx4.graphics = megatiles_new

	def remove_groups(self, ids):
		if len(ids) == 0:
			return
		groups = []

		for id, group in enumerate(self.tileset.cv5.groups):
			if id not in ids:
				groups.append(group)

		for i, doodad in enumerate(self.tileset.dddata.doodads):
			for j, id in enumerate(doodad):
				self.tileset.dddata.doodads[i][j] -= self.get_decrease_value(ids, id)

		self.tileset.cv5.groups = groups

	def swap_groups(self, id1, id2):
		temp = self.tileset.cv5.groups[id2]
		self.tileset.cv5.groups[id2] = self.tileset.cv5.groups[id1]
		self.tileset.cv5.groups[id1] = temp

		for i, doodad in enumerate(self.tileset.dddata.doodads):
			for j, id in enumerate(doodad):
				if id == id1:
					self.tileset.dddata.doodads[i][j] = id2
				if id == id2:
					self.tileset.dddata.doodads[i][j] = id1

	def clean(self, *_):
		if self.buttons['asc3topyai']['state'] != NORMAL or self.tiletype == TILETYPE_GROUP:
			return

		tiletype = "mega" if self.tiletype == TILETYPE_MEGA else "mini"
		unused = self.find_unused_tiles()

		if len(unused) == 0:
			askquestion("All good!", "There are no more unused " + tiletype + "tiles.", type=OK, icon=INFO)
			return

		if askquestion("Do you want to continue?", "There are " + str(len(unused)) + " unused " + tiletype + "tiles. Do you want to remove them? (This may take a while.)", type=YESNO, icon=QUESTION) == "yes":
			self.remove_tiles(unused)
			self.refresh()
			askquestion("Removing " + tiletype + "tiles completed.", "Removed " + str(len(unused)) + " unused " + tiletype + "tiles.", type=OK, icon=INFO)

	def find_unused_tiles(self):
		ids = []
		if self.tiletype == TILETYPE_MEGA:
			used_ids = set()
			for group in self.tileset.cv5.groups:
				for id in group[13]:
					used_ids.add(id)

			for id, mega in enumerate(self.tileset.vx4.graphics):
				if id not in used_ids:
					ids.append(id)

		elif self.tiletype == TILETYPE_MINI:
			used_ids = set()
			for graphic in self.tileset.vx4.graphics:
				for values in graphic:
					used_ids.add(values[0])

			for id, mini in enumerate(self.tileset.vr4.images):
				if id not in used_ids:
					ids.append(id)

		return ids

	def export_graphics(self, e=None):
		typename = ''
		if self.tiletype == TILETYPE_GROUP:
			typename = 'MegaTile Group'
		elif self.tiletype == TILETYPE_MEGA:
			typename = 'MegaTile'
		elif self.tiletype == TILETYPE_MINI:
			typename = 'MiniTile'
		path = PYTILE_SETTINGS.lastpath.graphics.select_file('export', self, 'Export %s Graphics' % typename, '.bmp', [('256 Color BMP','*.bmp'),('All Files','*')], save=True)
		if path:
			self.tileset.export_graphics(self.tiletype, path, sorted(self.palette.selected))
	def import_graphics(self, e=None):
		GraphicsImporter(self, self.tiletype, self.palette.selected)
	def imported_graphics(self, new_ids):
		TILE_CACHE.clear()
		self.update_title()
		self.update_state()
		self.palette.update_size()
		if len(new_ids):
			self.palette.select(new_ids)
			self.palette.scroll_to_selection()
		self.palette.draw_tiles(force=True)
		self.parent.update_ranges()
		self.mark_edited()

	def export_settings(self, e=None):
		if not len(self.palette.selected):
			return
		if self.tiletype == TILETYPE_GROUP:
			path = PYTILE_SETTINGS.lastpath.graphics.select_file('export', self, 'Export MegaTile Group Settings', '.txt', [('Text File','*.txt'),('All Files','*')], save=True)
			if path:
				self.tileset.export_settings(TILETYPE_GROUP, path, self.palette.selected)
		elif self.tiletype == TILETYPE_MEGA:
			MegaTileSettingsExporter(self, self.palette.selected)
	def import_settings(self, e=None):
		if not len(self.palette.selected):
			return
		SettingsImporter(self, self.tiletype, self.palette.selected)

	def edit(self, e=None):
		if not len(self.palette.selected):
			return
		if self.tiletype == TILETYPE_MEGA:
			MegaEditor(self, self.palette.selected[0])
		elif self.tiletype == TILETYPE_MINI:
			MiniEditor(self, self.palette.selected[0])

	def ok(self):
		PYTILE_SETTINGS.windows.palette.save_window_size(('group','mega','mini')[self.tiletype], self)
		if hasattr(self.delegate,'selecting'):
			self.delegate.selecting = None
		elif hasattr(self.delegate, 'megaload'):
			self.delegate.megaload()
		if self.edited and hasattr(self.delegate, 'mark_edited'):
			self.delegate.mark_edited()
		PAL[0] -= 1
		if not PAL[0]:
			TILE_CACHE.clear()
		PyMSDialog.ok(self)

	def cancel(self):
		self.ok()

class PyTILE(Tk):
	def __init__(self, guifile=None):
		#Window
		Tk.__init__(self)
		self.title('PyTILE %s' % LONG_VERSION)
		try:
			self.icon = os.path.join(BASE_DIR,'Images','PyTILE.ico')
			self.wm_iconbitmap(self.icon)
		except:
			self.icon = '@%s' % os.path.join(BASE_DIR, 'Images','PyTILE.xbm')
			self.wm_iconbitmap(self.icon)
		self.protocol('WM_DELETE_WINDOW', self.exit)
		ga.set_application('PyTILE', VERSIONS['PyTILE'])
		ga.track(GAScreen('PyTILE'))
		setup_trace(self, 'PyTILE')

		self.stat_txt = TBL.TBL()
		self.stat_txt_file = ''
		filen = PYTILE_SETTINGS.files.get('stat_txt', os.path.join(BASE_DIR, 'Libs', 'MPQ', 'rez', 'stat_txt.tbl'))
		while True:
			try:
				self.stat_txt.load_file(filen)
				break
			except:
				filen = PYTILE_SETTINGS.lastpath.select_file('general', self, 'Open stat_txt.tbl', '.tbl', [('StarCraft TBL files','*.tbl'),('All Files','*')])
				if not filen:
					sys.exit()

		self.loading_megas = False
		self.loading_minis = False
		self.tileset = None
		self.file = None
		self.edited = False
		self.megatile = None

		#Toolbar
		buttons = [
			('open', self.open, 'Open (Ctrl+O)', NORMAL, 'Ctrl+O'),
			('save', self.save, 'Save (Ctrl+S)', DISABLED, 'Ctrl+S'),
			('saveas', self.saveas, 'Save As (Ctrl+Alt+A)', DISABLED, 'Ctrl+Alt+A'),
			('close', self.close, 'Close (Ctrl+W)', DISABLED, 'Ctrl+W'),
			10,
			('up', self.expand, 'Expand the Tileset (Ctrl+E)', DISABLED, 'Ctrl+E'),
			('end', lambda *_: self.palette.draw_tiles(True), 'Force Redraw Palette (Ctrl+A)', NORMAL, 'Ctrl+A'),
			10,
			('find', lambda *_: self.choose(TILETYPE_GROUP), 'MegaTile Group Palette (Ctrl+P)', DISABLED, 'Ctrl+P'),
			10,
			('register', self.register, 'Set as default *.cv5, *.cv5ex editor (Windows Only)', [DISABLED,NORMAL][win_reg], ''),
			('help', self.help, 'Help (F1)', NORMAL, 'F1'),
			('about', self.about, 'About PyTILE', NORMAL, ''),
			10,
			('exit', self.exit, 'Exit (Alt+F4)', NORMAL, 'Alt+F4'),
		]
		self.buttons = {}
		toolbar = Frame(self)
		for btn in buttons:
			if isinstance(btn, tuple):
				image = PhotoImage(file=os.path.join(BASE_DIR,'Images','%s.gif' % btn[0]))
				button = Button(toolbar, image=image, width=20, height=20, command=btn[1], state=btn[3])
				button.image = image
				button.tooltip = Tooltip(button, btn[2])
				button.pack(side=LEFT)
				self.buttons[btn[0]] = button
				a = btn[4]
				if a:
					if not a.startswith('F'):
						self.bind('<%s%s>' % (a[:-1].replace('Ctrl','Control').replace('+','-'), a[-1].lower()), btn[1])
					else:
						self.bind('<%s>' % a, btn[1])
			else:
				Frame(toolbar, width=btn).pack(side=LEFT)
		toolbar.pack(side=TOP, padx=1, pady=1, fill=X)

		self.disable = []

		self.megatilee = IntegerVar(0,[0,4095],callback=lambda id: self.change(TILETYPE_MEGA, int(id)))
		self.index = IntegerVar(0,[0,65535],callback=self.group_values_changed)
		self.flags = IntegerVar(0,[0,15],callback=self.group_values_changed)
		self.groundheight = IntegerVar(0,[0,15],callback=self.group_values_changed)
		self.buildable = IntegerVar(0,[0,15],callback=self.group_values_changed)
		self.buildable2 = IntegerVar(0,[0,15],callback=self.group_values_changed)
		self.edgeleft = IntegerVar(0,[0,65535],callback=self.group_values_changed)
		self.edgeright = IntegerVar(0,[0,65535],callback=self.group_values_changed)
		self.edgeup = IntegerVar(0,[0,65535],callback=self.group_values_changed)
		self.edgedown = IntegerVar(0,[0,65535],callback=self.group_values_changed)
		self.hasup = IntegerVar(0,[0,65535],callback=self.group_values_changed)
		self.hasdown = IntegerVar(0,[0,65535],callback=self.group_values_changed)
		self.unknown9 = IntegerVar(0,[0,65535],callback=self.group_values_changed)
		self.unknown11 = IntegerVar(0,[0,65535],callback=self.group_values_changed)
		self.doodad = False

		self.apply_all_exclude_nulls = IntVar()
		self.apply_all_exclude_nulls.set(PYTILE_SETTINGS.mega_edit.get('apply_all_exclude_nulls', True))

		self.copy_mega_height = IntVar()
		self.copy_mega_height.set(PYTILE_SETTINGS['copy'].mega.get('height', True))
		self.copy_mega_height.trace('w', self.action_states)
		self.copy_mega_walkable = IntVar()
		self.copy_mega_walkable.set(PYTILE_SETTINGS['copy'].mega.get('walkable', True))
		self.copy_mega_walkable.trace('w', self.action_states)
		self.copy_mega_sight = IntVar()
		self.copy_mega_sight.set(PYTILE_SETTINGS['copy'].mega.get('sight', True))
		self.copy_mega_sight.trace('w', self.action_states)
		self.copy_mega_ramp = IntVar()
		self.copy_mega_ramp.set(PYTILE_SETTINGS['copy'].mega.get('ramp', True))
		self.copy_mega_ramp.trace('w', self.action_states)

		self.copy_tilegroup_flags = IntVar()
		self.copy_tilegroup_flags.set(PYTILE_SETTINGS['copy'].tilegroup.get('flags', True))
		self.copy_tilegroup_flags.trace('w', self.action_states)
		self.copy_tilegroup_buildable = IntVar()
		self.copy_tilegroup_buildable.set(PYTILE_SETTINGS['copy'].tilegroup.get('buildable', True))
		self.copy_tilegroup_buildable.trace('w', self.action_states)
		self.copy_tilegroup_hasup = IntVar()
		self.copy_tilegroup_hasup.set(PYTILE_SETTINGS['copy'].tilegroup.get('hasup', True))
		self.copy_tilegroup_hasup.trace('w', self.action_states)
		self.copy_tilegroup_edges = IntVar()
		self.copy_tilegroup_edges.set(PYTILE_SETTINGS['copy'].tilegroup.get('edges', True))
		self.copy_tilegroup_edges.trace('w', self.action_states)
		self.copy_tilegroup_unknown9 = IntVar()
		self.copy_tilegroup_unknown9.set(PYTILE_SETTINGS['copy'].tilegroup.get('unknown9', True))
		self.copy_tilegroup_unknown9.trace('w', self.action_states)
		self.copy_tilegroup_index = IntVar()
		self.copy_tilegroup_index.set(PYTILE_SETTINGS['copy'].tilegroup.get('index', True))
		self.copy_tilegroup_index.trace('w', self.action_states)
		self.copy_tilegroup_buildable2 = IntVar()
		self.copy_tilegroup_buildable2.set(PYTILE_SETTINGS['copy'].tilegroup.get('buildable2', True))
		self.copy_tilegroup_buildable2.trace('w', self.action_states)
		self.copy_tilegroup_hasdown = IntVar()
		self.copy_tilegroup_hasdown.set(PYTILE_SETTINGS['copy'].tilegroup.get('hasdown', True))
		self.copy_tilegroup_hasdown.trace('w', self.action_states)
		self.copy_tilegroup_ground_height = IntVar()
		self.copy_tilegroup_ground_height.set(PYTILE_SETTINGS['copy'].tilegroup.get('ground_height', True))
		self.copy_tilegroup_ground_height.trace('w', self.action_states)
		self.copy_tilegroup_unknown11 = IntVar()
		self.copy_tilegroup_unknown11.set(PYTILE_SETTINGS['copy'].tilegroup.get('unknown11', True))
		self.copy_tilegroup_unknown11.trace('w', self.action_states)

		self.copy_doodadgroup_doodad = IntVar()
		self.copy_doodadgroup_doodad.set(PYTILE_SETTINGS['copy'].doodadgroup.get('doodad', True))
		self.copy_doodadgroup_doodad.trace('w', self.action_states)
		self.copy_doodadgroup_overlay = IntVar()
		self.copy_doodadgroup_overlay.set(PYTILE_SETTINGS['copy'].doodadgroup.get('overlay', True))
		self.copy_doodadgroup_overlay.trace('w', self.action_states)
		self.copy_doodadgroup_buildable = IntVar()
		self.copy_doodadgroup_buildable.set(PYTILE_SETTINGS['copy'].doodadgroup.get('buildable', True))
		self.copy_doodadgroup_buildable.trace('w', self.action_states)
		self.copy_doodadgroup_unknown1 = IntVar()
		self.copy_doodadgroup_unknown1.set(PYTILE_SETTINGS['copy'].doodadgroup.get('unknown1', True))
		self.copy_doodadgroup_unknown1.trace('w', self.action_states)
		self.copy_doodadgroup_unknown6 = IntVar()
		self.copy_doodadgroup_unknown6.set(PYTILE_SETTINGS['copy'].doodadgroup.get('unknown6', True))
		self.copy_doodadgroup_unknown6.trace('w', self.action_states)
		self.copy_doodadgroup_unknown8 = IntVar()
		self.copy_doodadgroup_unknown8.set(PYTILE_SETTINGS['copy'].doodadgroup.get('unknown8', True))
		self.copy_doodadgroup_unknown8.trace('w', self.action_states)
		self.copy_doodadgroup_unknown12 = IntVar()
		self.copy_doodadgroup_unknown12.set(PYTILE_SETTINGS['copy'].doodadgroup.get('unknown12', True))
		self.copy_doodadgroup_unknown12.trace('w', self.action_states)
		self.copy_doodadgroup_index = IntVar()
		self.copy_doodadgroup_index.set(PYTILE_SETTINGS['copy'].doodadgroup.get('index', True))
		self.copy_doodadgroup_index.trace('w', self.action_states)
		self.copy_doodadgroup_ground_height = IntVar()
		self.copy_doodadgroup_ground_height.set(PYTILE_SETTINGS['copy'].doodadgroup.get('ground_height', True))
		self.copy_doodadgroup_ground_height.trace('w', self.action_states)
		self.copy_doodadgroup_group_string_id = IntVar()
		self.copy_doodadgroup_group_string_id.set(PYTILE_SETTINGS['copy'].doodadgroup.get('group_string_id', True))
		self.copy_doodadgroup_group_string_id.trace('w', self.action_states)

		self.findimage = PhotoImage(file=os.path.join(BASE_DIR,'Images','find.gif'))

		mid = Frame(self)
		self.palette = TilePaletteView(mid, TILETYPE_GROUP, delegate=self, multiselect=False, sub_select=True, pytile=self)
		self.palette.pack(side=LEFT, fill=Y)

		settings = Frame(mid)
		self.groupid = LabelFrame(settings, text='MegaTile Group')
		self.flow_view = FlowView(self.groupid, width=300)
		self.flow_view.pack(fill=BOTH, expand=1, padx=2)

		OPTION_RADIO = 0
		OPTION_CHECK = 1
		def options_editor(name, tooltip, variable, options):
			group = LabelFrame(self.flow_view.content_view, text=name)
			c = Frame(group)
			raw_tooltip = ''
			for option_name,option_value,option_tooltip,option_type,option_mask in options:
				raw_tooltip += '\n  %d = %s' % (option_value, option_name)
				if option_type == OPTION_CHECK and not option_value:
					continue
				f = Frame(c)
				if option_type == OPTION_CHECK:
					self.disable.append(MaskCheckbutton(f, text=option_name, variable=variable, value=option_value, state=DISABLED))
				else:
					self.disable.append(MaskedRadiobutton(f, text=option_name, variable=variable, value=option_value, mask=option_mask if option_mask else variable.range[1], state=DISABLED))
				self.disable[-1].pack(side=LEFT)
				tip(self.disable[-1], name, tooltip + '\n\n%s:\n  %s' % (option_name, option_tooltip))
				f.pack(side=TOP, fill=X)
			f = Frame(c)
			Label(f, text='Raw:').pack(side=LEFT)
			self.disable.append(Entry(f, textvariable=variable, font=couriernew, width=len(str(variable.range[1])), state=DISABLED))
			self.disable[-1].pack(side=LEFT)
			tip(self.disable[-1], name, tooltip + '\n\nRaw:' + raw_tooltip)
			f.pack(side=TOP, fill=X)
			c.pack(padx=2,pady=2)
			return group
		def entries_editor(name, tooltip, rows):
			group = LabelFrame(self.flow_view.content_view, text=name)
			f = Frame(group)
			for r,row in enumerate(rows):
				for c,(field_name, variable, field_tooltip) in enumerate(row):
					Label(f, text=field_name + ':').grid(column=c*2, row=r, sticky=E)
					self.disable.append(Entry(f, textvariable=variable, font=couriernew, width=len(str(variable.range[1])), state=DISABLED))
					self.disable[-1].grid(column=c*2+1, row=r, sticky=W)
					if tooltip:
						tip(self.disable[-1], name, tooltip + '\n\n%s:\n  %s' % (field_name, field_tooltip))
					else:
						tip(self.disable[-1], field_name, field_tooltip)
			f.pack(padx=2,pady=2)
			return group
		def string_editor(name, tooltip, variable):
			group = LabelFrame(self.flow_view.content_view, text=name)
			f = Frame(group)
			Label(f, text='String:').grid(column=0,row=0, sticky=E)
			self.disable.append(DropDown(f, IntVar(), ['None'] + [TBL.decompile_string(s) for s in self.stat_txt.strings], variable, width=20))
			self.disable[-1].grid(sticky=W+E, column=1,row=0)
			tip(self.disable[-1], name, tooltip)
			f.grid_columnconfigure(1, weight=1)
			Label(f, text='Raw:').grid(column=0,row=1, sticky=E)
			self.disable.append(Entry(f, textvariable=variable, font=couriernew, width=len(str(variable.range[1])), state=DISABLED))
			self.disable[-1].grid(sticky=W, column=1,row=1)
			tip(self.disable[-1], name, tooltip)
			f.pack(fill=BOTH, expand=1, padx=2,pady=2)
			return group
		def actions_editor(name, actions):
			group = LabelFrame(self.flow_view.content_view, text=name)
			f = Frame(group)
			for action_name,tooltip,callback in actions:
				self.disable.append(Button(f, text=action_name, command=callback))
				self.disable[-1].pack(fill=X, pady=(0,2))
				tip(self.disable[-1], action_name, tooltip)
			f.pack(fill=BOTH, expand=1, padx=2,pady=(2,0))
			return group

		self.editor_configs = []

		self.normal_editors = []
		group = options_editor('Flags', 'Unknown', self.flags, (
			('Normal?', 0, 'Unknown', OPTION_RADIO, None),
			('Edge?', 1, 'Unknown', OPTION_RADIO, None),
			('Cliff?', 4, 'Unknown', OPTION_RADIO, None)
		))
		self.normal_editors.append(group)
		group = options_editor('Buildable', 'Default buildability property', self.buildable, (
			('Buildable', 0, 'All buildings buildable', OPTION_RADIO, None),
			('Creep', 4, 'Only Zerg buildings buildable', OPTION_RADIO, None),
			('Unbuildable', 8, 'No buildings buildable', OPTION_RADIO, None)
		))
		self.normal_editors.append(group)
		group = options_editor('Buildable 2', 'Buildability for Beacons/Start Location', self.buildable2, (
			('Default', 0, 'Use default buildability', OPTION_RADIO, None),
			('Buildable', 8, 'Beacons and Start Location are Buildable', OPTION_RADIO, None)
		))
		self.normal_editors.append(group)
		group = options_editor('Has Up', 'Edge piece has rows above it. Not completely understood.', self.hasup, (
			('Basic edge piece', 1, 'Unknown', OPTION_RADIO, None),
			('Right edge piece', 2, 'Unknown', OPTION_RADIO, None),
			('Left edge piece', 3, 'Unknown', OPTION_RADIO, None)
		))
		self.normal_editors.append(group)
		group = options_editor('Has Down', 'Edge piece has rows below it. Not completely understood.', self.hasdown, (
			('Basic edge piece', 1, 'Unknown', OPTION_RADIO, None),
			('Right edge piece', 2, 'Unknown', OPTION_RADIO, None),
			('Left edge piece', 3, 'Unknown', OPTION_RADIO, None)
		))
		self.normal_editors.append(group)
		group = entries_editor('Edges?', 'Unknown. Seems to be related to surrounding tiles & ISOM.', (
			(('Left?', self.edgeleft, 'Unknown.'), ('Up?', self.edgeup, 'Unknown.')),
			(('Right?', self.edgeright, 'Unknown.'), ('Down?', self.edgedown, 'Unknown.')),
		))
		self.normal_editors.append(group)
		group = entries_editor('Misc.', None, (
			(('Index', self.index, 'Group Index? Not completely understood'),),
			(('Ground Height', self.groundheight, 'Shows ground height. Does not seem to be completely valid.\n  May be used by StarEdit/deprecated?'),),
		))
		self.normal_editors.append(group)
		group = entries_editor('Unknowns', None, (
			(('Unknown 9', self.unknown9, 'Unknown'),),
			(('Unknown 11', self.unknown11, 'Unknown'),)
		))
		self.normal_editors.append(group)
		megatile_group = LabelFrame(self.flow_view.content_view, text='MegaTile')
		f = Frame(megatile_group)
		Label(f, text='ID:').pack(side=LEFT)
		self.disable.append(Entry(f, textvariable=self.megatilee, font=couriernew, width=len(str(self.megatilee.range[1]))+4, state=DISABLED))
		self.disable[-1].pack(side=LEFT, padx=2)
		tip(self.disable[-1], 'MegaTile ID', 'ID for the selected MegaTile in the current MegaTile Group')
		self.disable.append(Button(f, image=self.findimage, width=20, height=20, command=lambda i=1: self.choose(i), state=DISABLED))
		self.disable[-1].pack(side=LEFT, padx=2)
		f.pack(side=TOP, fill=X, padx=3)
		def megatile_apply_all_pressed():
			menu = Menu(self, tearoff=0)
			mode = self.mega_editor.edit_mode.get()
			name = [None,None,'Height','Walkability','Blocks View','Ramp(?)'][mode]
			menu.add_command(label="Apply %s flags to Megatiles in Group (Control+Shift+%s)" % (name, name[0]), command=lambda m=mode: self.megatile_apply_all(mode))
			menu.add_command(label="Apply all flags to Megatiles in Group (Control+Shift+A)", command=self.megatile_apply_all)
			menu.add_command(label="Change all Megatiles to NULL in Group (Control+Shift+N)", command=self.megatile_null_all)
			menu.add_separator()
			menu.add_checkbutton(label="Exclude Null Tiles", variable=self.apply_all_exclude_nulls)
			menu.post(*self.winfo_pointerxy())
		self.apply_all_btn = Button(megatile_group, text='Apply to Megas', state=DISABLED, command=megatile_apply_all_pressed)
		self.disable.append(self.apply_all_btn)
		self.apply_all_btn.pack(side=BOTTOM, padx=3, pady=(0,3), fill=X)
		bind = (
			('H', lambda e: self.megatile_apply_all(MEGA_EDIT_MODE_HEIGHT)),
			('W', lambda e: self.megatile_apply_all(MEGA_EDIT_MODE_WALKABILITY)),
			('B', lambda e: self.megatile_apply_all(MEGA_EDIT_MODE_VIEW_BLOCKING)),
			('R', lambda e: self.megatile_apply_all(MEGA_EDIT_MODE_RAMP)),
			('A', lambda e: self.megatile_apply_all(None)),
			('N', lambda e: self.megatile_null_all())
		)
		for key,func in bind:
			self.bind('<Control-Shift-%s>' % key, func)
		self.mega_editor = MegaEditorView(megatile_group, self, palette_editable=True, pytile=self)
		self.mega_editor.set_enabled(False)
		self.mega_editor.pack(side=TOP, padx=3, pady=(3,0))
		self.normal_editors.append(megatile_group)
		copy_mega_group = LabelFrame(self.flow_view.content_view, text='Manage MegaTile Flags')
		opts = (
			('Height', self.copy_mega_height),
			('Walkable', self.copy_mega_walkable),
			('Blocks Sight', self.copy_mega_sight),
			('Ramp', self.copy_mega_ramp)
		)
		for n,(name,var) in enumerate(opts):
			check = Checkbutton(copy_mega_group, text=name, variable=var, anchor=W, state=NORMAL)
			check.grid(sticky=W, column=int(n/2), row=int(n%2))
			#self.disable.append(check)

		self.copy_mega_btn = Button(copy_mega_group, text='Copy (Ctrl+Shift+C)', state=DISABLED, command=self.copy_mega)
		self.bind('<Control-Shift-C>', self.copy_mega)
		self.copy_mega_btn.grid(sticky=E)

		btn = Button(copy_mega_group, text='Paste (Ctrl+Shift+V)', state=DISABLED, command=self.paste_mega)
		self.bind('<Control-Shift-V>', self.paste_mega)
		btn.grid(sticky=E)
		self.disable.append(btn)
		self.normal_editors.append(copy_mega_group)
		copy_tilegroup_group = LabelFrame(self.flow_view.content_view, text='Copy Group Settings')
		opts = (
			(
				('Flags', self.copy_tilegroup_flags),
				('Buildable', self.copy_tilegroup_buildable),
				('Has Up', self.copy_tilegroup_hasup),
				('Edges', self.copy_tilegroup_edges),
				('Unknown 9', self.copy_tilegroup_unknown9),
			),
			(
				('Index', self.copy_tilegroup_index),
				('Buildable 2', self.copy_tilegroup_buildable2),
				('Has Down', self.copy_tilegroup_hasdown),
				('Ground Height', self.copy_tilegroup_ground_height),
				('Unknown 11', self.copy_tilegroup_unknown11)
			)
		)
		for c,rows in enumerate(opts):
			for r,(name,var) in enumerate(rows):
				check = Checkbutton(copy_tilegroup_group, text=name, variable=var, anchor=W, state=DISABLED)
				check.grid(column=c,row=r, sticky=W)
				#self.disable.append(check)
		def copy_tilegroup(*args):
			if not self.tileset:
				return
			options = {}
			if group < 1024:
				options = {
					'groups_export_index': self.copy_tilegroup_index.get(),
					'groups_export_buildable': self.copy_tilegroup_buildable.get(),
					'groups_export_flags': self.copy_tilegroup_flags.get(),
					'groups_export_buildable2': self.copy_tilegroup_buildable2.get(),
					'groups_export_ground_height': self.copy_tilegroup_ground_height.get(),
					'groups_export_edge_left': self.copy_tilegroup_edges.get(),
					'groups_export_edge_up': self.copy_tilegroup_edges.get(),
					'groups_export_edge_right': self.copy_tilegroup_edges.get(),
					'groups_export_edge_down': self.copy_tilegroup_edges.get(),
					'groups_export_unknown9': self.copy_tilegroup_unknown9.get(),
					'groups_export_has_up': self.copy_tilegroup_hasup.get(),
					'groups_export_unknown11': self.copy_tilegroup_unknown11.get(),
					'groups_export_has_down': self.copy_tilegroup_hasdown.get(),
				}
			else:
				options = {
					'groups_export_index': self.copy_doodadgroup_index.get(),
					'groups_export_buildable': self.copy_doodadgroup_buildable.get(),
					'groups_export_unknown1': self.copy_doodadgroup_unknown1.get(),
					'groups_export_overlay_flags': self.copy_doodadgroup_overlay.get(),
					'groups_export_ground_height': self.copy_doodadgroup_ground_height.get(),
					'groups_export_overlay_id': self.copy_doodadgroup_overlay.get(),
					'groups_export_unknown6': self.copy_doodadgroup_unknown6.get(),
					'groups_export_doodad_group_string': self.copy_doodadgroup_group_string_id.get(),
					'groups_export_unknown8': self.copy_doodadgroup_unknown8.get(),
					'groups_export_dddata_id': self.copy_doodadgroup_doodad.get(),
					'groups_export_doodad_width': self.copy_doodadgroup_doodad.get(),
					'groups_export_doodad_height': self.copy_doodadgroup_doodad.get(),
					'groups_export_unknown12': self.copy_doodadgroup_unknown12.get(),
				}
			if not max(options.values):
				return
			group = self.palette.selected[0]
			f = FFile()
			self.tileset.export_settings(TILETYPE_GROUP, f, [group], options)
			self.clipboard_clear()
			self.clipboard_append(f.data)
		self.copy_tilegroup_btn = Button(copy_tilegroup_group, text='Copy (Ctrl+Alt+C)', state=DISABLED, command=copy_tilegroup)
		self.bind('<Control-Alt-c>', copy_tilegroup)
		self.copy_tilegroup_btn.grid(column=0,row=5, sticky=E+W)
		def paste_tilegroup(*args):
			if not self.tileset:
				return
			group = self.palette.selected[0]
			settings = self.clipboard_get()
			try:
				self.tileset.import_settings(TILETYPE_GROUP, settings, [group])
			except PyMSError, e:
				ErrorDialog(self, e)
				return
			self.megaload()
			self.mark_edited()
		btn = Button(copy_tilegroup_group, text='Paste (Ctrl+Alt+V)', state=DISABLED, command=paste_tilegroup)
		self.bind('<Control-Alt-v>', paste_tilegroup)
		btn.grid(column=1,row=5, sticky=E+W)
		#self.disable.append(btn)
		self.normal_editors.append(copy_tilegroup_group)

		settings_group = LabelFrame(self.flow_view.content_view, text='Tileset View Settings')

		self.show_minitiles = BooleanVar()
		self.show_minitiles.set(PYTILE_SETTINGS['tileset_view'].get('show_minitiles', False))

		def updateFlags(*_):
			self.palette.draw_tiles(True)
			self.mega_editor.draw()

		show_minitiles = Checkbutton(settings_group, text="Show Minitile Flags", variable=self.show_minitiles, command=updateFlags)
		show_minitiles.grid(column=1,row=1,sticky=N+W)

		self.show_buildable = BooleanVar()
		self.show_buildable.set(PYTILE_SETTINGS['tileset_view'].get('show_buildable', False))

		show_buildable = Checkbutton(settings_group, text="Show Buildable Flag", variable=self.show_buildable, command=updateFlags)
		show_buildable.grid(column=1,row=2,sticky=N+W)

		self.edit_minitiles = BooleanVar()
		self.edit_minitiles.set(PYTILE_SETTINGS['tileset_view'].get('edit_minitiles', True))
		edit_minitiles = Checkbutton(settings_group, text="Paint Minitile Flags", variable=self.edit_minitiles)
		edit_minitiles.grid(column=1,row=3,sticky=N+W)

		def setZoom(scale):
			scroll = self.palette.canvas.yview()[0]
			self.palette.setScale(scale)
			self.palette.canvas.yview_moveto(scroll)

		def update_group_select():
			group_select = self.group_select.get()
			if group_select != self.palette.multiselect:
				self.palette.multiselect = group_select
				self.palette.selected = [self.palette.selected[0]]
				updateFlags()

		self.group_select = BooleanVar()
		self.group_select.set(PYTILE_SETTINGS['tileset_view'].get('group_select', False))
		group_select = Checkbutton(settings_group, text="Group Multi Selection", variable=self.group_select, command=lambda: update_group_select())
		group_select.grid(column=1,row=4,sticky=N+W)
		update_group_select()


		Label(settings_group, text='Zoom:').grid(column=1, row=5, sticky=N+W)
		self.zoom = IntegerVar(0, [1, 3], callback=lambda scale: setZoom(scale))
		self.zoom.set(PYTILE_SETTINGS['tileset_view'].get('zoom', 1))
		zoom = Entry(settings_group, textvariable=self.zoom, font=couriernew, width=17)
		zoom.grid(column=1,row=6,sticky=N+W)
		setZoom(self.zoom.get())

		Label(settings_group, text='Style:').grid(column=1, row=7, sticky=N+W)
		self.style = IntegerVar(0, [0, 2], callback=updateFlags)
		self.style.set(PYTILE_SETTINGS['tileset_view'].get('style', STYLE_BOXES))
		styles = ["Boxes", "Dots", "Dots and Boxes"]
		style = DropDown(settings_group, self.style, styles, width=15)
		style.grid(column=1, row=8, sticky=N+W)

		flagGenerator = LabelFrame(self.flow_view.content_view, text='Flag Generator')

		heights = ["Low", "Medium", "High"]
		self.traversable = IntegerVar(0, [0,2])
		self.nontraversable = IntegerVar(1, [0,2])

		Label(flagGenerator, text='Walkability <-> Height').grid(column=1,row=1,sticky=N+W, padx=3, pady=3)
		Label(flagGenerator, text='Traversable').grid(column=1,row=2,sticky=N+W, padx=3, pady=3)
		DropDown(flagGenerator, self.traversable, heights, width=15).grid(column=1, row=3, sticky=N+W, padx=3, pady=3)
		Label(flagGenerator, text='Non-Traversable').grid(column=2,row=2,sticky=N+W, padx=3, pady=3)
		DropDown(flagGenerator, self.nontraversable, heights, width=15).grid(column=2, row=3, sticky=N+W, padx=3, pady=3)

		def preset(offset):
			self.traversable.set(min(0 + offset, 2))
			self.nontraversable.set(min(1 + offset, 2))
		presets = LabelFrame(flagGenerator, text="")
		Button(presets, text='Preset 1', command=lambda: preset(0)).pack(side=LEFT)
		Button(presets, text='Preset 2', command=lambda: preset(1)).pack(side=LEFT)
		presets.grid(column=2, row=1, sticky=N+W, padx=3, pady=3)

		self.disable.append(Button(flagGenerator, text='Generate Height from Walkability (Ctrl+G)', state=DISABLED, command=self.generate_height_current))
		self.disable[-1].grid(column=1, row=4, sticky=N+W, padx=3, pady=3, columnspan=2)
		self.disable.append(Button(flagGenerator, text='Generate Walkability from Height (Ctrl+Shift+G)', state=DISABLED, command=self.generate_walkability_current))
		self.disable[-1].grid(column=1, row=5, sticky=N+W, padx=3, pady=3, columnspan=2)
		self.bind("<Control-g>", self.generate_height_current)
		self.bind("<Control-Shift-G>", self.generate_walkability_current)

		self.disable.append(Button(copy_mega_group, text='Mirror Horizontally (Ctrl+Y)', state=DISABLED, command=lambda: self.mirror(False)))
		self.disable[-1].grid(column=1, row=2, sticky=N + W, padx=3, pady=3, columnspan=2)
		self.disable.append(Button(copy_mega_group, text='Mirror Vertically (Ctrl+U)', state=DISABLED, command=lambda: self.mirror(True)))
		self.disable[-1].grid(column=1, row=3, sticky=N + W, padx=3, pady=3, columnspan=2)
		self.bind("<Control-y>", lambda e: self.mirror(False))
		self.bind("<Control-u>", lambda e: self.mirror(True))


		utility = LabelFrame(self.flow_view.content_view, text='Flag Utility')
		Button(utility, text='Shift Height Up', command=lambda: self.shift_height_current(True)).grid(column=0,row=0, sticky=E+W)
		Button(utility, text='Shift Height Down', command=lambda: self.shift_height_current(False)).grid(column=0,row=1, sticky=E+W)
		#self.bind("<Shift-Up>", self.shift_height_current(True))
		#self.bind("<Shift-Down>", self.shift_height_current(False))

		self.normal_editors.append(settings_group)
		self.normal_editors.append(flagGenerator)
		self.normal_editors.append(utility)

		self.doodad_editors = []

		group = entries_editor('Doodad', 'Basic doodad properties', (
			(('ID', self.edgeright, 'Each doodad must have a unique Doodad ID.\n  All MegaTile Groups in the doodad must have the same ID.'),),
			(('Width', self.edgeup, 'Total width of the doodad in MegaTiles'),),
			(('Height', self.edgedown, 'Total height of the doodad in MegaTiles'),),
		))
		self.doodad_editors.append(group)
		group = options_editor('Has Overlay', 'Doodad overlay settings', self.buildable2, (
			('None', 0, 'No overlay', OPTION_RADIO, 3),
			('Sprites.dat', 1, 'The overlay ID is a Sprites.dat reference.', OPTION_RADIO, 3),
			('Units.dat', 2, 'The overlay ID is a Units.dat reference', OPTION_RADIO, 3),
			('Flipped', 4, 'The overlay is flipped.', OPTION_CHECK, None),
		))
		self.doodad_editors.append(group)
		group = entries_editor('Overlay', None, (
			(('ID', self.hasup, 'Sprite or Unit ID (depending on the Has Overlay flag) of the doodad overlay.'),),
		))
		self.doodad_editors.append(group)
		group = options_editor('Buildable', 'Default buildability property', self.buildable, (
			('Buildable', 0, 'All buildings buildable', OPTION_CHECK, None),
			('Unknown', 1, 'Unknown', OPTION_CHECK, None),
			('Creep', 4, 'Only Zerg buildings buildable', OPTION_RADIO, 12),
			('Unbuildable', 8, 'No buildings buildable', OPTION_RADIO, 12),
		))
		self.doodad_editors.append(group)
		group = entries_editor('Unknowns', None, (
			(('Unknown 1', self.flags, 'Unknown'),),
			(('Unknown 6', self.hasdown, 'Unknown'),),
			(('Unknown 8', self.unknown9, 'Unknown'),),
			(('Unknown 12', self.unknown11, 'Unknown'),)
		))
		self.doodad_editors.append(group)
		group = entries_editor('Misc.', None, (
			(('Index', self.index, 'Group Index? Not completely understood'),),
			(('Ground Height', self.groundheight, 'Shows ground height. Does not seem to be completely valid.\n  May be used by StarEdit/deprecated?'),),
		))
		self.doodad_editors.append(group)
		group = string_editor('Group', 'Doodad group string from stat_txt.tbl', self.edgeleft)
		self.doodad_editors.append(group)
		self.editor_configs.append((group, {'weight': 1}))
		group = actions_editor('Other', (
			('Placeability', 'Modify which megatile groups the doodad must be placed on.', self.placeability),
			('Apply All', 'Apply these MegaTile Group settings to all the MegaTile Groups with the same Doodad ID', self.doodad_apply_all)
		))
		self.doodad_editors.append(group)
		self.doodad_editors.append(megatile_group)
		self.doodad_editors.append(copy_mega_group)
		copy_doodadgroup_group = LabelFrame(self.flow_view.content_view, text='Copy Group Settings')
		opts = (
			(
				('Doodad', self.copy_doodadgroup_doodad),
				('Buildable', self.copy_doodadgroup_buildable),
				('Index', self.copy_doodadgroup_index),
				('Unknown 1', self.copy_doodadgroup_unknown1),
				('Unknown 6', self.copy_doodadgroup_unknown6),
			),
			(
				('Overlay', self.copy_doodadgroup_overlay),
				('Ground Height', self.copy_doodadgroup_ground_height),
				('Group String', self.copy_doodadgroup_group_string_id),
				('Unknown 8', self.copy_doodadgroup_unknown8),
				('Unknown 12', self.copy_doodadgroup_unknown12),
			)
		)
		for c,rows in enumerate(opts):
			for r,(name,var) in enumerate(rows):
				check = Checkbutton(copy_doodadgroup_group, text=name, variable=var, anchor=W, state=DISABLED)
				check.grid(column=c,row=r, sticky=W)
				#self.disable.append(check)
		self.copy_doodadgroup_btn = Button(copy_doodadgroup_group, text='Copy (Ctrl+Alt+C)', state=DISABLED, command=copy_tilegroup)
		self.bind('<Control-Alt-c>', copy_tilegroup)
		self.copy_doodadgroup_btn.grid(column=0,row=5, sticky=E+W)
		btn = Button(copy_doodadgroup_group, text='Paste (Ctrl+Alt+V)', state=DISABLED, command=paste_tilegroup)
		self.bind('<Control-Alt-v>', paste_tilegroup)
		btn.grid(column=1,row=5, sticky=E+W)
		#self.disable.append(btn)
		self.doodad_editors.append(copy_doodadgroup_group)
		self.flow_view.add_subviews(self.normal_editors, padx=2)

		self.groupid.pack(fill=BOTH, expand=1, padx=5, pady=5)
		settings.pack(side=LEFT, fill=BOTH, expand=1)
		mid.pack(fill=BOTH, expand=1)

		self.doodad_editors.append(settings_group)
		self.doodad_editors.append(flagGenerator)
		self.doodad_editors.append(utility)


		#Statusbar
		self.status = StringVar()
		self.expanded = StringVar()
		statusbar = Frame(self)
		Label(statusbar, textvariable=self.status, bd=1, relief=SUNKEN, width=45, anchor=W).pack(side=LEFT, padx=1)
		image = PhotoImage(file=os.path.join(BASE_DIR,'Images','save.gif'))
		self.editstatus = Label(statusbar, image=image, bd=0, state=DISABLED)
		self.editstatus.image = image
		self.editstatus.pack(side=LEFT, padx=1, fill=Y)
		Label(statusbar, textvariable=self.expanded, bd=1, relief=SUNKEN, anchor=W).pack(side=LEFT, expand=1, padx=1, fill=X)
		self.status.set('Load a Tileset.')
		statusbar.pack(side=BOTTOM, fill=X)

		PYTILE_SETTINGS.windows.load_window_size('main', self)

		if guifile:
			self.open(file=guifile)

		start_new_thread(check_update, (self, 'PyTILE'))

	def tile_palette_get_tileset(self):
		return self.tileset

	def tile_palette_get_tile(self):
		return self.get_tile

	def tile_palette_binding_widget(self):
		return self

	def tile_palette_bind_updown(self):
		return False

	def tile_palette_selection_changed(self):
		self.megaload()

	def unsaved(self):
		if self.tileset and self.edited:
			file = self.file
			if not file:
				file = 'Unnamed.cv5'
			save = askquestion(parent=self, title='Save Changes?', message="Save changes to '%s'?" % file, default=YES, type=YESNOCANCEL)
			if save != 'no':
				if save == 'cancel':
					return True
				if self.file:
					self.save()
				else:
					self.saveas()

	def action_states(self, *args, **kwargs):
		file = [NORMAL,DISABLED][not self.tileset]
		for btn in ['save','saveas','close','find']:
			self.buttons[btn]['state'] = file

		if not self.tileset:
			self.buttons['up']['state'] = DISABLED
		else:
			self.buttons['up']['state'] = [NORMAL, DISABLED][self.tileset.vx4.expanded]

		for w in self.disable:
			w['state'] = file
		self.mega_editor.set_enabled(self.tileset != None)
		if self.tileset and self.tileset.vx4.expanded:
			self.expanded.set('VX4 Expanded')
		self.copy_mega_btn['state'] = [DISABLED,NORMAL][not not self.tileset and (self.copy_mega_height.get() or self.copy_mega_walkable.get() or self.copy_mega_sight.get() or self.copy_mega_ramp.get())]
		#self.copy_tilegroup_btn['state'] = [DISABLED,NORMAL][not not self.tileset and (self.copy_tilegroup_flags.get() or self.copy_tilegroup_buildable.get() or self.copy_tilegroup_hasup.get() or self.copy_tilegroup_edges.get() or self.copy_tilegroup_unknown9.get() or self.copy_tilegroup_index.get() or self.copy_tilegroup_buildable2.get() or self.copy_tilegroup_hasdown.get() or self.copy_tilegroup_ground_height.get() or self.copy_tilegroup_unknown11.get())]
		#self.copy_doodadgroup_btn['state'] = [DISABLED,NORMAL][not not self.tileset and (self.copy_doodadgroup_doodad.get() or self.copy_doodadgroup_overlay.get() or self.copy_doodadgroup_buildable.get() or self.copy_doodadgroup_unknown1.get() or self.copy_doodadgroup_unknown6.get() or self.copy_doodadgroup_unknown8.get() or self.copy_doodadgroup_unknown12.get() or self.copy_doodadgroup_index.get() or self.copy_doodadgroup_ground_height.get() or self.copy_doodadgroup_group_string_id.get())]

	def mark_edited(self, edited=True):
		self.edited = edited
		self.editstatus['state'] = [DISABLED,NORMAL][edited]

	def get_tile(self, id, cache=False):
		to_photo = [Tilesets.megatile_to_photo,Tilesets.minitile_to_photo][isinstance(id,tuple) or isinstance(id,list)]
		if cache:
			if not id in TILE_CACHE:
				if len(TILE_CACHE) > 2048:
					for tileID in list(TILE_CACHE.keys())[0:128]:
						del TILE_CACHE[tileID]
				TILE_CACHE[id] = to_photo(self.tileset, id)
			return TILE_CACHE[id]
		return to_photo(self.tileset, id)

	def megatile_null_all(self):
		if not self.tileset:
			return
		if self.palette.multiselect:
			for group in sorted(self.palette.selected):
				for i in range(16):
					self.megatile_null(group, i)
		else:
			for i in range(16):
				self.megatile_null(self.palette.selected[0], i)
		self.update_palette_null()

	def megatile_null_current(self):
		if not self.tileset:
			return
		self.megatile_null(self.palette.selected[0], self.palette.sub_selection)
		self.update_palette_null()

	def update_palette_null(self):
		self.palette.draw_tiles(force=True)
		self.palette.select(self.palette.selected)
		self.mark_edited()

	def megatile_null(self, group, tile):
		self.tileset.cv5.groups[group][13][tile] = 0

	def get_mega_id(self, group, n):
		return self.tileset.cv5.groups[group][13][n]

	def int_to_height(self, i):
		if (i == 1):
			return HEIGHT_MID
		if (i == 2):
			return HEIGHT_HIGH
		return HEIGHT_LOW

	def generate_height(self, group, n, reversed=False):
		id = self.get_mega_id(group, n)
		if id == 0 and self.palette.multiselect:
			return False

		nontraversable = self.int_to_height(self.nontraversable.get())
		traversable = self.int_to_height(self.traversable.get())

		edited = False
		for n in xrange(16):
			flags = self.tileset.vf4.flags[id][n]
			if reversed:
				new_flags = flags & ~1
				new_flags |= [0, 1][flags & traversable != 0]
			else:
				new_flags = flags & ~(HEIGHT_MID | HEIGHT_HIGH)
				new_flags |= [nontraversable, traversable][flags & 1]
			if new_flags != flags:
				self.tileset.vf4.flags[id][n] = new_flags
				edited = True
		return edited

	def generate_height_group(self, current_group, reversed=False):
		edited = False
		for n in xrange(16):
			edited = self.generate_height(current_group, n, reversed) or edited
		return edited

	def generate_height_current(self, *_):
		if not self.tileset:
			return

		edited = False
		if self.palette.multiselect:
			for i in self.palette.selected:
				edited = self.generate_height_group(i) or edited
		else:
			edited = self.generate_height(self.palette.selected[0], self.palette.sub_selection)

		if edited:
			self.palette.draw_tiles(force=True)
			self.mega_editor.draw()
			self.mark_edited()

	def generate_walkability_current(self, *_):
		if not self.tileset:
			return

		edited = False
		if self.palette.multiselect:
			for i in self.palette.selected:
				edited = self.generate_height_group(i, True) or edited
		else:
			edited = self.generate_height(self.palette.selected[0], self.palette.sub_selection, True)

		if edited:
			self.palette.draw_tiles(force=True)
			self.mega_editor.draw()
			self.mark_edited()

	def get_mask(self):
		height = HEIGHT_MID | HEIGHT_HIGH if self.copy_mega_height.get() else 0
		walkable = 1 if self.copy_mega_walkable.get() else 0
		sight = 8 if self.copy_mega_sight.get() else 0
		ramp = 16 if self.copy_mega_ramp.get() else 0

		return height | walkable | sight | ramp

	def apply_mask(self, original_flags, new_flags, mask):
		return (new_flags & mask) | (original_flags & ~mask)

	def xy_to_index(self, x, y):
		return int(y * 4 + x)

	def index_to_xy(self, index):
		return (int(index % 4), int(floor(index / 4)))

	def flipped(self, i):
		if i == 0:
			return 3
		if i == 3:
			return 0
		if i == 2:
			return 1
		if i == 1:
			return 2

	def shift_height_current(self, up):
		if not self.tileset:
			return
		edited = False
		if self.palette.multiselect:
			for group in sorted(self.palette.selected):
				for n in xrange(16):
					edited = self.shift_height(group, n, up) or edited
		else:
			edited = self.shift_height(self.palette.selected[0], self.palette.sub_selection, up)

		if edited:
			self.palette.draw_tiles(force=True)
			self.mega_editor.draw()
			self.mark_edited()

	def shift_height(self, group, n, up):
		edited = False
		id = self.get_mega_id(group, n)
		if id == 0 and self.palette.multiselect:
			return False

		for n in xrange(16):
			flags = self.tileset.vf4.flags[id][n]
			# 6 = low (0) + mid (2) + high (4)
			new_flags = flags & ~6
			height_flag = flags & 6
			if up:
				new_flags = new_flags | min(height_flag + 2, 4)
			else:
				new_flags = new_flags | max(height_flag - 2, 0)
			if new_flags != flags:
				self.tileset.vf4.flags[id][n] = new_flags
				edited = True

		return edited

	def mirror(self, vertically=False):
		if not self.tileset:
			return
		edited = False

		if self.palette.multiselect:
			edited = True

			nulltile_ids = []
			original_flags = []
			for group_id in sorted(self.palette.selected):
				for tile_id in xrange(16):
					megatile_id = self.get_mega_id(group_id, tile_id)
					if megatile_id == 0:
						nulltile_ids.append(len(original_flags))
						original_flags.append([])
						continue
					self.mirror_tile(megatile_id, vertically)
					original_flags.append(self.tileset.vf4.flags[megatile_id])

			for group_n, group_id in enumerate(sorted(self.palette.selected)):
				for tile_id in xrange(16):
					megatile_id = self.get_mega_id(group_id, tile_id)
					if vertically:
						flipped_id = len(original_flags) - (group_n + 1) * 16 + tile_id
					else: # horizontally
						flipped_id = group_n * 16 + (15 - tile_id)
					if flipped_id in nulltile_ids:
						continue
					self.tileset.vf4.flags[megatile_id] = original_flags[flipped_id]
		else:
			group = self.palette.selected[0]
			tile = self.palette.sub_selection

			tile_edited = self.mirror_tile(self.get_mega_id(group, tile), vertically)
			edited = tile_edited or edited

		if edited:
			self.palette.draw_tiles(force=True)
			self.mega_editor.draw()
			self.mark_edited()

	def mirror_tile(self, id, vertically=False):
		if id == 0:
			return False
		edited = False
		mega_copy = self.tileset.vf4.flags[id][:]
		mask = self.get_mask()
		for n in xrange(16):
			x, y = self.index_to_xy(n)
			if vertically:
				y = self.flipped(y)
			else:
				x = self.flipped(x)
			n2 = self.xy_to_index(x, y)

			flags = self.tileset.vf4.flags[id][n]
			new_flags = self.apply_mask(flags, self.tileset.vf4.flags[id][n2], mask)
			if new_flags != flags:
				mega_copy[n] = new_flags
				edited = True

		if edited:
			self.tileset.vf4.flags[id] = mega_copy
		return edited

	def copy_mega(self, *_):
		if not self.tileset:
			return

		if self.palette.multiselect:
			self.clipboard_group_count = len(self.palette.selected)
			self.clipboard_megatile_flags = []
			for group in sorted(self.palette.selected):
				for tile in xrange(16):
					id = self.get_mega_id(group, tile)
					for n in xrange(16):
						self.clipboard_megatile_flags.append(self.tileset.vf4.flags[id][n])
		else:
			group = self.palette.selected[0]
			tile = self.palette.sub_selection
			id = self.get_mega_id(group, tile)

			self.clipboard_group_count = 1
			self.clipboard_megatile_flags = []
			for n in xrange(16):
				self.clipboard_megatile_flags.append(self.tileset.vf4.flags[id][n])


	def paste_single(self, id, mask, offset=0):
		edited = False
		new_tile_flags = self.tileset.vf4.flags[id][:]
		flag_count = len(self.clipboard_megatile_flags)
		for n in xrange(16):
			flags = self.tileset.vf4.flags[id][n]
			new_flags = self.apply_mask(flags, self.clipboard_megatile_flags[(n + offset * 16) % flag_count], mask)
			if flags != new_flags:
				new_tile_flags[n] = new_flags
				edited = True
		if edited:
			self.tileset.vf4.flags[id] = new_tile_flags
		return edited

	def paste_mega(self, *_):
		if not self.tileset or not hasattr(self, "clipboard_megatile_flags"):
			return

		mask = self.get_mask()
		edited = False

		if self.palette.multiselect:
			offset = 0
			for group in sorted(self.palette.selected):
				for tile in xrange(16):
					id = self.get_mega_id(group, tile)
					ret = self.paste_single(id, mask, offset)
					edited = ret or edited
					offset += 1

		else:
			group = self.palette.selected[0]
			tile = self.palette.sub_selection
			id = self.get_mega_id(group, tile)

			ret = self.paste_single(id, mask)
			edited = ret or edited



		if edited:
			self.palette.draw_tiles(force=True)
			self.mega_editor.draw()
			self.mark_edited()

	def megatile_apply_all(self, mode=None):
		if not self.tileset:
			return

		edited = False

		## Needs tile selection in group multiselect mode to work
		#if self.palette.multiselect:
		#	for group in sorted(self.palette.selected):
		#	edited = self.megatile_apply_all_specific(group) or edited
		#else:
		#	edited = self.megatile_apply_all_specific(self.palette.selected[0])

		if self.palette.multiselect:
			return
		edited = self.megatile_apply_all_specific(self.palette.selected[0], mode)

		if edited:
			self.palette.draw_tiles(force=True)
			self.mark_edited()

	def megatile_apply_all_specific(self, group, mode=None):
		copy_mask = ~0
		if mode == MEGA_EDIT_MODE_HEIGHT:
			copy_mask = HEIGHT_MID | HEIGHT_HIGH
		elif mode == MEGA_EDIT_MODE_WALKABILITY:
			copy_mask = 1
		elif mode == MEGA_EDIT_MODE_VIEW_BLOCKING:
			copy_mask = 8
		elif mode == MEGA_EDIT_MODE_RAMP:
			copy_mask = 16
		copy_mega = self.tileset.cv5.groups[group][13][self.palette.sub_selection]
		edited = False
		for m in self.tileset.cv5.groups[group][13]:
			if m == copy_mega or (m == 0 and self.apply_all_exclude_nulls.get()):
				continue
			for n in xrange(16):
				copy_flags = self.tileset.vf4.flags[copy_mega][n]
				flags = self.tileset.vf4.flags[m][n]
				new_flags = (flags & ~copy_mask) | (copy_flags & copy_mask)
				if new_flags != flags:
					self.tileset.vf4.flags[m][n] = new_flags
					edited = True
		return edited

	def doodad_apply_all(self):
		doodad_id = self.edgeright.get()
		settings = self.tileset.cv5.groups[self.palette.selected[0]][:-1]
		for i in range(1024, len(self.tileset.cv5.groups)):
			if i != self.palette.selected[0] and self.tileset.cv5.groups[i][9] == doodad_id:
				self.tileset.cv5.groups[i][:-1] = settings
		self.palette.draw_tiles(force=True)
		self.mark_edited()

	def mega_edit_mode_updated(self, mode):
		if mode == MEGA_EDIT_MODE_MINI or mode == MEGA_EDIT_MODE_FLIP:
			self.apply_all_btn.pack_forget()
		else:
			self.apply_all_btn.pack()

	def update_group_label(self):
		d = ['',' - Doodad'][self.palette.selected[0] >= 1024]
		if self.palette.multiselect:
			sorted_selection = sorted(self.palette.selected)
			self.groupid['text'] = 'MegaTile Group [%s-%s%s]' % (sorted_selection[0], sorted_selection[-1], d)
		else:
			self.groupid['text'] = 'MegaTile Group [%s%s]' % (self.palette.selected[0],d)

	def megaload(self):
		self.loading_megas = True
		group = self.tileset.cv5.groups[self.palette.selected[0]]
		mega = group[13][self.palette.sub_selection]
		if self.megatilee.get() != mega:
			self.megatilee.check = False
			self.megatilee.set(mega)
			self.megatilee.check = True
		if self.palette.selected[0] >= 1024:
			if not self.doodad:
				self.flow_view.remove_all_subviews()
				self.flow_view.add_subviews(self.doodad_editors, padx=2)
				for view,config in self.editor_configs:
					self.flow_view.update_subview_config(view, **config)
				self.doodad = True
			o = [self.index,self.buildable,self.flags,self.buildable2,self.groundheight,self.hasup,self.hasdown,self.edgeleft,self.unknown9,self.edgeright,self.edgeup,self.edgedown,self.unknown11]
		else:
			if self.doodad:
				self.flow_view.remove_all_subviews()
				self.flow_view.add_subviews(self.normal_editors, padx=2)
				for view,config in self.editor_configs:
					self.flow_view.update_subview_config(view, **config)
				self.doodad = False
			o = [self.index,self.buildable,self.flags,self.buildable2,self.groundheight,self.edgeleft,self.edgeup,self.edgeright,self.edgedown,self.unknown9,self.hasup,self.unknown11,self.hasdown]
		for n,v in enumerate(o):
			v.set(group[n])
		self.miniload()
		self.update_group_label()
		self.loading_megas = False

	def miniload(self):
		self.mega_editor.set_megatile(self.tileset.cv5.groups[self.palette.selected[0]][13][self.palette.sub_selection])

	def group_values_changed(self, *_):
		if not self.tileset or self.loading_megas:
			return

		if self.palette.multiselect:
			for i in sorted(self.palette.selected):
				group = self.tileset.cv5.groups[i]
				self.change_group_value(group)
		else:
			group = self.tileset.cv5.groups[self.palette.selected[0]]
			self.change_group_value(group)

		if self.show_buildable.get():
			self.palette.draw_tiles(True)
			self.mega_editor.draw()

		self.mark_edited()

	def change_group_value(self, group):
		group[0] = self.index.get()
		if self.palette.selected[0] >= 1024:
			o = [self.buildable, self.flags, self.buildable2, self.groundheight, self.hasup, self.hasdown, self.edgeleft, self.unknown9, self.edgeright, self.edgeup, self.edgedown, self.unknown11]
		else:
			o = [self.buildable, self.flags, self.buildable2, self.groundheight, self.edgeleft, self.edgeup, self.edgeright, self.edgedown, self.unknown9, self.hasup, self.unknown11, self.hasdown]
		for n, v in enumerate(o):
			group[n + 1] = v.get()

	def choose(self, i):
		TilePalette(self, i, [
				self.palette.selected[0],
				self.tileset.cv5.groups[self.palette.selected[0]][13][self.palette.sub_selection]
			][i],
			editing=True)

	def change(self, tiletype, id):
		if not self.tileset:
			return
		if tiletype == TILETYPE_GROUP:
			self.palette.select(id, sub_select=0, scroll_to=True)
		elif tiletype == TILETYPE_MEGA and not self.loading_megas:
			self.tileset.cv5.groups[self.palette.selected[0]][13][self.palette.sub_selection] = id
			self.palette.draw_tiles(force=True)
			self.mega_editor.set_megatile(id)
			self.mark_edited()

	def placeability(self):
		Placeability(self, self.edgeright.get())

	def update_ranges(self):
		self.megatilee.setrange([0,len(self.tileset.vf4.flags)-1])
		self.mega_editor.update_mini_range()
		self.palette.update_size(True)

	def open(self, key=None, file=None):
		if not self.unsaved():
			if file == None:
				file = PYTILE_SETTINGS.lastpath.tileset.select_file('open', self, 'Open Complete Tileset', '.cv5 .cv5ex', [('Complete Tileset','*.cv5 *.cv5ex'),('All Files','*')])
				if not file:
					return
			tileset = Tilesets.Tileset()
			try:
				tileset.load_file(file)
			except PyMSError, e:
				ErrorDialog(self, e)
				return
			self.tileset = tileset
			self.file = file
			self.status.set('Load successful!')
			self.mark_edited(False)
			self.action_states()
			self.update_ranges()
			self.palette.update_size()
			self.palette.select(0)
			if self.tileset.vx4.expanded:
				PYTILE_SETTINGS.dont_warn.warn('expanded_vx4', self, 'This tileset is using an expanded vx4 file.')
			if self.tileset.cv5.expanded:
				PYTILE_SETTINGS.dont_warn.warn('expanded_cv5', self, 'This tileset is using an expanded cv5 file.')

	def save(self, key=None):
		if key and self.buttons['save']['state'] != NORMAL:
			return
		if self.file == None:
			self.saveas()
			return
		if not overwriteFile(self, self.file):
			return
		try:
			self.tileset.save_file(self.file)
			self.status.set('Save Successful!')
			self.mark_edited(False)
		except PyMSError, e:
			ErrorDialog(self, e)

	def saveas(self, key=None):
		if key and self.buttons['saveas']['state'] != NORMAL:
			return
		file = PYTILE_SETTINGS.lastpath.tileset.select_file('save', self, 'Save Tileset As', '.cv5', [('Complete Tileset','*.cv5 *.cv5ex'),('All Files','*')], save=True)
		if not file:
			return True
		self.file = file
		self.save()

	def close(self, key=None):
		if key and self.buttons['close']['state'] != NORMAL:
			return
		if not self.unsaved():
			self.tileset = None
			self.file = None
			self.status.set('Load or create a Tileset.')
			self.mark_edited(False)
			self.groupid['text'] = 'MegaTile Group'
			if self.doodad:
				self.doodads.pack_forget()
				self.tiles.pack(side=TOP)
				self.doodad = False
			self.mega_editor.set_megatile(None)
			for v in [self.index,self.megatilee,self.buildable,self.flags,self.buildable2,self.groundheight,self.edgeleft,self.edgeup,self.edgeright,self.edgedown,self.unknown9,self.hasup,self.unknown11,self.hasdown]:
				v.set(0)
			self.palette.draw_tiles()
			self.action_states()

	def expand(self, e):
		if self.buttons['up']['state'] != NORMAL:
			return

		self.tileset.vx4.expanded = True
		self.mark_edited()
		askquestion(title="Success", message="The tileset have been expanded successfully. Please save your tileset.", type=OK)

	def register(self, e=None):
		try:
			register_registry('PyTILE','','cv5',os.path.join(BASE_DIR, 'PyTILE.pyw'),os.path.join(BASE_DIR,'Images','PyTILE.ico'))
			register_registry('PyTILE','','cv5ex',os.path.join(BASE_DIR, 'PyTILE.pyw'),os.path.join(BASE_DIR,'Images','PyTILE.ico'))
		except PyMSError, e:
			ErrorDialog(self, e)

	def help(self, e=None):
		webbrowser.open('file:///%s' % os.path.join(BASE_DIR, 'Docs', 'PyTILE.html'))

	def about(self, key=None):
		AboutDialog(self, 'PyTILE', LONG_VERSION, [('FaRTy1billion','Tileset file specs and HawtTiles.')])

	def exit(self, e=None):
		if not self.unsaved():
			PYTILE_SETTINGS.windows.save_window_size('main', self)
			PYTILE_SETTINGS.mega_edit.apply_all_exclude_nulls = not not self.apply_all_exclude_nulls.get()
			PYTILE_SETTINGS['copy'].mega.height = not not self.copy_mega_height.get()
			PYTILE_SETTINGS['copy'].mega.walkable = not not self.copy_mega_walkable.get()
			PYTILE_SETTINGS['copy'].mega.sight = not not self.copy_mega_sight.get()
			PYTILE_SETTINGS['copy'].mega.ramp = not not self.copy_mega_ramp.get()
			PYTILE_SETTINGS['copy'].tilegroup.flags = not not self.copy_tilegroup_flags.get()
			PYTILE_SETTINGS['copy'].tilegroup.buildable = not not self.copy_tilegroup_buildable.get()
			PYTILE_SETTINGS['copy'].tilegroup.hasup = not not self.copy_tilegroup_hasup.get()
			PYTILE_SETTINGS['copy'].tilegroup.edges = not not self.copy_tilegroup_edges.get()
			PYTILE_SETTINGS['copy'].tilegroup.unknown9 = not not self.copy_tilegroup_unknown9.get()
			PYTILE_SETTINGS['copy'].tilegroup.index = not not self.copy_tilegroup_index.get()
			PYTILE_SETTINGS['copy'].tilegroup.buildable2 = not not self.copy_tilegroup_buildable2.get()
			PYTILE_SETTINGS['copy'].tilegroup.hasdown = not not self.copy_tilegroup_hasdown.get()
			PYTILE_SETTINGS['copy'].tilegroup.ground_height = not not self.copy_tilegroup_ground_height.get()
			PYTILE_SETTINGS['copy'].tilegroup.unknown11 = not not self.copy_tilegroup_unknown11.get()
			PYTILE_SETTINGS['copy'].doodadgroup.doodad = not not self.copy_doodadgroup_doodad.get()
			PYTILE_SETTINGS['copy'].doodadgroup.overlay = not not self.copy_doodadgroup_overlay.get()
			PYTILE_SETTINGS['copy'].doodadgroup.buildable = not not self.copy_doodadgroup_buildable.get()
			PYTILE_SETTINGS['copy'].doodadgroup.unknown1 = not not self.copy_doodadgroup_unknown1.get()
			PYTILE_SETTINGS['copy'].doodadgroup.unknown6 = not not self.copy_doodadgroup_unknown6.get()
			PYTILE_SETTINGS['copy'].doodadgroup.unknown8 = not not self.copy_doodadgroup_unknown8.get()
			PYTILE_SETTINGS['copy'].doodadgroup.unknown12 = not not self.copy_doodadgroup_unknown12.get()
			PYTILE_SETTINGS['copy'].doodadgroup.index = not not self.copy_doodadgroup_index.get()
			PYTILE_SETTINGS['copy'].doodadgroup.ground_height = not not self.copy_doodadgroup_ground_height.get()
			PYTILE_SETTINGS['copy'].doodadgroup.group_string_id = not not self.copy_doodadgroup_group_string_id.get()
			PYTILE_SETTINGS['mega_edit'].mode = self.mega_editor.edit_mode.get()
			PYTILE_SETTINGS['tileset_view'].show_minitiles = self.show_minitiles.get()
			PYTILE_SETTINGS['tileset_view'].show_buildable = self.show_buildable.get()
			PYTILE_SETTINGS['tileset_view'].edit_minitiles = self.edit_minitiles.get()
			PYTILE_SETTINGS['tileset_view'].group_select = self.group_select.get()
			PYTILE_SETTINGS['tileset_view'].style = self.style.get()
			PYTILE_SETTINGS['tileset_view'].zoom = self.zoom.get()
			PYTILE_SETTINGS.save()
			self.destroy()

def main():
	import sys
	if not sys.argv or (len(sys.argv) == 1 and os.path.basename(sys.argv[0]).lower() in ['','pytile.py','pytile.pyw','pytile.exe']):
		gui = PyTILE()
		startup(gui)
	else:
		p = optparse.OptionParser(usage='usage: PyTILE [options]', version='PyTILE %s' % LONG_VERSION)
		# p.add_option('-v', '--vf4', metavar='FILE', help='Choose a palette for GRP to BMP conversion [default: %default]', default='')
		# p.add_option('-p', '--palette', metavar='FILE', help='Choose a palette for GRP to BMP conversion [default: %default]', default='Units.pal')
		# p.add_option('-g', '--grptobmps', action='store_true', dest='convert', help="Converting from GRP to BMP's [default]", default=True)
		# p.add_option('-b', '--bmpstogrp', action='store_false', dest='convert', help="Converting from BMP's to GRP")
		# p.add_option('-u', '--uncompressed', action='store_true', help="Used to signify if the GRP is uncompressed (both to and from BMP) [default: Compressed]", default=False)
		# p.add_option('-o', '--onebmp', action='store_true', help='Used to signify that you want to convert a GRP to one BMP file. [default: Multiple]', default=False)
		# p.add_option('-f', '--frames', type='int', help='Used to signify you are using a single BMP with alll frames, and how many frames there are.', default=0)
		p.add_option('--gui', help="Opens a file with the GUI", default='')
		opt, args = p.parse_args()
		if opt.gui:
			gui = PyTILE(opt.gui)
			startup(gui)

if __name__ == '__main__':
	main()

