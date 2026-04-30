from crm_app.models.action import Action
from crm_app.models.company import Company
from crm_app.models.contact import Contact
from crm_app.models.custom_field import FieldDefinition, FieldValue
from crm_app.models.opportunity import Opportunity
from crm_app.models.offer import Offer
from crm_app.models.sample import Sample

all_models = (Action, Company, Contact, FieldDefinition, FieldValue, Opportunity, Offer, Sample)

__all__ = [
    "Action",
    "Company",
    "Contact",
    "FieldDefinition",
    "FieldValue",
    "Opportunity",
    "Offer",
    "Sample",
    "all_models",
]
