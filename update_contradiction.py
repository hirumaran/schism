import re
with open('apps/api/app/models/contradiction.py', 'r') as f:
    content = f.read()

replacement = """
    def model_post_init(self, __context: Any) -> None:
        if self.pair_key is None:
            self.pair_key = build_pair_key(self.paper_a_id, self.paper_b_id)

    @property
    def claim_a_text(self) -> str | None:
        return self.paper_a_claim

    @property
    def claim_b_text(self) -> str | None:
        return self.paper_b_claim

    @property
    def paper_a_title(self) -> str:
        return self.paper_a.title if self.paper_a else ""

    @property
    def paper_b_title(self) -> str:
        return self.paper_b.title if self.paper_b else ""

    @property
    def contradiction_score(self) -> float:
        return self.score

    @property
    def contradiction_type(self) -> str:
        return self.type.value if self.type else ""
"""
if "def model_post_init(self, __context: Any) -> None:" in content:
    content = content.replace("""    def model_post_init(self, __context: Any) -> None:
        if self.pair_key is None:
            self.pair_key = build_pair_key(self.paper_a_id, self.paper_b_id)""", replacement)

    # Need to import computed_field
    if "from pydantic import BaseModel, ConfigDict, Field" in content:
        content = content.replace("from pydantic import BaseModel, ConfigDict, Field", "from pydantic import BaseModel, ConfigDict, Field, computed_field")
    
    # Actually wait, I need to add @computed_field to the properties to ensure they are returned in the API
    content = content.replace("@property", "@computed_field\n    @property")

with open('apps/api/app/models/contradiction.py', 'w') as f:
    f.write(content)
