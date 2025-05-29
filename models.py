from sqlalchemy import Column, Integer, String, Float, ForeignKey, Table
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# Association table for many-to-many relationship between Items and People
item_person = Table(
    'item_person', Base.metadata,
    Column('item_id', ForeignKey('items.id'), primary_key=True),
    Column('person_id', ForeignKey('people.id'), primary_key=True)
)

class Receipt(Base):
    __tablename__ = 'receipts'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    tax_tip = Column(Float)
    items = relationship('Item', back_populates='receipt')
    people = relationship('Person', back_populates='receipt')

class Item(Base):
    __tablename__ = 'items'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    price = Column(Float)
    receipt_id = Column(Integer, ForeignKey('receipts.id'))
    receipt = relationship('Receipt', back_populates='items')
    people = relationship('Person', secondary=item_person, back_populates='items')

class Person(Base):
    __tablename__ = 'people'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    receipt_id = Column(Integer, ForeignKey('receipts.id'))
    receipt = relationship('Receipt', back_populates='people')
    items = relationship('Item', secondary=item_person, back_populates='people')
