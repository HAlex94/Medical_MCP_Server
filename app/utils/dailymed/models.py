"""
DailyMed Data Models

Defines data classes for structured DailyMed drug information.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class DrugResult:
    """Represents a basic drug search result from DailyMed."""
    drug_name: str
    url: str
    set_id: Optional[str] = None
    manufacturer: Optional[str] = None
    application_no: Optional[str] = None


@dataclass
class Section:
    """Represents a section in a drug label."""
    title: str
    content: str


@dataclass
class DrugData:
    """Represents detailed drug information from DailyMed."""
    title: Optional[str] = None
    manufacturer: Optional[str] = None
    active_ingredients: List[Dict[str, str]] = field(default_factory=list)
    drug_class: Optional[str] = None
    full_sections: Dict[str, str] = field(default_factory=dict)
    tables: Dict[str, List[List[Dict[str, str]]]] = field(default_factory=dict)
    downloads: Dict[str, str] = field(default_factory=dict)
    set_id: Optional[str] = None
    application_number: Optional[str] = None
    ndc_codes: List[str] = field(default_factory=list)
    search_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_error(self) -> bool:
        """Check if the data contains an error."""
        return 'error' in self.__dict__ and self.error is not None


@dataclass
class DrugError:
    """Represents an error in retrieving drug information."""
    error: str
    url: Optional[str] = None
    query: Optional[str] = None
