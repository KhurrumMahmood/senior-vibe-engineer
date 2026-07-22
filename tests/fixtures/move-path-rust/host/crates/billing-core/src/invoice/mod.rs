mod consumer;
pub mod service;

pub use service::InvoiceService;

pub fn parent_constructed() -> service::InvoiceService {
    service::InvoiceService
}

pub fn sibling_constructed() -> InvoiceService {
    consumer::construct()
}
