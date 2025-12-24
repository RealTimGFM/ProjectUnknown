
from __future__ import annotations
from pydantic import BaseModel, Field, EmailStr, HttpUrl, ConfigDict
from typing import List, Optional

class DateSpan(BaseModel):
    start: Optional[str] = Field(default=None, description="YYYY-MM or None")
    end: Optional[str] = Field(default=None, description="YYYY-MM or 'Present' or None")
    months: Optional[int] = None

class ProjectItem(BaseModel):
    title: str
    role: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    dates: DateSpan = Field(default_factory=DateSpan)
    bullets: list[str] = Field(default_factory=list)

class ExperienceItem(BaseModel):
    title: Optional[str] = ""
    company: Optional[str] = ""
    location: Optional[str] = ""
    dates: DateSpan = DateSpan()
    bullets: List[str] = []
    technologies: List[str] = []
    confidence: float = 0.0

class EducationItem(BaseModel):
    degree: Optional[str] = ""
    field: Optional[str] = ""
    school: Optional[str] = ""
    location: Optional[str] = ""
    dates: DateSpan = DateSpan()
    gpa: Optional[str] = None

class Contact(BaseModel):
    name: Optional[str] = ""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[HttpUrl] = None
    github: Optional[HttpUrl] = None
    websites: List[HttpUrl] = []

class Resume(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    contact: Contact = Contact()
    summary: Optional[str] = ""
    skills: List[str] = []
    experience: List[ExperienceItem] = []
    education: List[EducationItem] = []
    certifications: List[str] = []
    languages: List[str] = []
    raw_text: str = ""
    projects: list[ProjectItem] = Field(default_factory=list)
    flags: dict = {}
