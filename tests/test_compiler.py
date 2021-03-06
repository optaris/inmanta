"""
    Copyright 2016 Inmanta

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

    Contact: code@inmanta.com
"""

import re

from inmanta.ast import Namespace
from inmanta.ast.statements import define, Literal
from inmanta.parser.plyInmantaParser import parse
from inmanta.parser import ParserException
from inmanta.ast.statements.define import DefineImplement, DefineTypeConstraint, DefineTypeDefault, DefineIndex, DefineEntity
from inmanta.ast.constraint.expression import GreaterThan, Regex, Not, And, IsDefined
from inmanta.ast.statements.generator import Constructor
from inmanta.ast.statements.call import FunctionCall
from inmanta.ast.statements.assign import Assign, CreateList, IndexLookup, StringFormat
from inmanta.ast.variables import Reference, AttributeReference
import pytest


def parse_code(model_code: str):
    root_ns = Namespace("__root__")
    main_ns = Namespace("__config__")
    main_ns.parent = root_ns
    statements = parse(main_ns, "test", model_code)

    return statements


def test_define_empty():
    parse_code("""""")


def test_define_entity():
    """Test the definition of entities
    """
    statements = parse_code("""
entity Test:
end
entity Other:
string hello
end
entity Other:
 \"\"\"XX
 \"\"\"
end
""")

    assert len(statements) == 3

    stmt = statements[0]
    assert isinstance(stmt, define.DefineEntity)
    assert stmt.name == "Test"
    assert stmt.parents == ["std::Entity"]
    assert len(stmt.attributes) == 0
    assert stmt.comment is None


def test_extend_entity():
    """Test extending entities
    """
    statements = parse_code("""
entity Test extends Foo:
end
""")

    assert len(statements) == 1

    stmt = statements[0]
    assert stmt.parents == ["Foo"]


def test_complex_entity():
    """Test definition of a complex entity
    """
    documentation = "This entity has documentation"
    statements = parse_code("""
entity Test extends Foo, foo::sub::Bar:
    \"\"\" %s
    \"\"\"
    string hello
    bool bar = true
    number ten=5
end
""" % documentation)

    assert len(statements) == 1

    stmt = statements[0]
    assert len(stmt.parents) == 2
    assert stmt.parents == ["Foo", "foo::sub::Bar"]
    assert stmt.comment.strip() == documentation
    assert len(stmt.attributes) == 3

    for ad in stmt.attributes:
        assert isinstance(ad.type, str)
        assert isinstance(ad.name, str)

    assert stmt.attributes[0].name == "hello"
    assert stmt.attributes[1].name == "bar"
    assert stmt.attributes[2].name == "ten"

    assert stmt.attributes[1].default.execute(None, None, None)

    assert stmt.attributes[2].default.execute(None, None, None) == 5


def test_relation():
    """Test definition of relations
    """
    statements = parse_code("""
Test tests [0:] -- [5:10] Foo bars
""")

    assert len(statements) == 1
    rel = statements[0]

    assert len(rel.left) == 3
    assert len(rel.right) == 3

    assert rel.left[0] == "Test"
    assert rel.right[0] == "Foo"

    assert rel.left[1] == "tests"
    assert rel.right[1] == "bars"

    assert rel.left[2] == (0, None)
    assert rel.right[2] == (5, 10)
    assert statements[0].requires is None


def test_relation_2():
    """Test definition of relations
    """
    statements = parse_code("""
Test tests [3] -- [:10] Foo bars
""")

    assert len(statements) == 1
    rel = statements[0]

    assert len(rel.left) == 3
    assert len(rel.right) == 3

    assert rel.left[0] == "Test"
    assert rel.right[0] == "Foo"

    assert rel.left[1] == "tests"
    assert rel.right[1] == "bars"

    assert rel.left[2] == (3, 3)
    assert rel.right[2] == (None, 10)
    assert statements[0].requires is None


def test_new_relation():
    """Test definition of relations
    """
    statements = parse_code("""
Test.bar [1] -- Foo.tests [5:10]
""")

    assert len(statements) == 1, "Should return four statements"
    rel = statements[0]

    assert len(rel.left) == 3
    assert len(rel.right) == 3

    assert rel.left[0] == "Test"
    assert rel.right[0] == "Foo"

    assert rel.left[1] == "tests"
    assert rel.right[1] == "bar"

    assert rel.left[2] == (5, 10)
    assert rel.right[2] == (1, 1)
    assert statements[0].requires is None


def test_new_relation_with_annotations():
    """Test definition of relations
    """
    statements = parse_code("""
Test.bar [1] foo,bar Foo.tests [5:10]
""")

    assert len(statements) == 1, "Should return four statements"
    rel = statements[0]

    assert len(rel.left) == 3
    assert len(rel.right) == 3

    assert rel.left[0] == "Test"
    assert rel.right[0] == "Foo"

    assert rel.left[1] == "tests"
    assert rel.right[1] == "bar"

    assert rel.left[2] == (5, 10)
    assert rel.right[2] == (1, 1)
    assert statements[0].requires is None
    assert len(rel.annotations) == 2
    assert rel.annotations[0].name == "foo"
    assert rel.annotations[1].name == "bar"


def test_new_relation_unidir():
    """Test definition of relations
    """
    statements = parse_code("""
Test.bar [1] -- Foo
""")

    assert len(statements) == 1, "Should return four statements"
    rel = statements[0]

    assert len(rel.left) == 3
    assert len(rel.right) == 3

    assert rel.left[0] == "Test"
    assert rel.right[0] == "Foo"

    assert rel.left[1] is None
    assert rel.right[1] == "bar"

    assert rel.left[2] is None
    assert rel.right[2] == (1, 1)
    assert statements[0].requires is None


def test_new_relation_with_annotations_unidir():
    """Test definition of relations
    """
    statements = parse_code("""
Test.bar [1] foo,bar Foo
""")

    assert len(statements) == 1, "Should return four statements"
    rel = statements[0]

    assert len(rel.left) == 3
    assert len(rel.right) == 3

    assert rel.left[0] == "Test"
    assert rel.right[0] == "Foo"

    assert rel.left[1] is None
    assert rel.right[1] == "bar"

    assert rel.left[2] is None
    assert rel.right[2] == (1, 1)
    assert statements[0].requires is None
    assert len(rel.annotations) == 2
    assert rel.annotations[0].name == "foo"
    assert rel.annotations[1].name == "bar"


def test_implementation():
    """Test the definition of implementations
    """
    statements = parse_code("""
implementation test for Test:
end
""")

    assert len(statements) == 1
    assert len(statements[0].block.get_stmts()) == 0
    assert statements[0].name == "test"
    assert isinstance(statements[0].entity, str)

    statements = parse_code("""
implementation test for Test:
    std::File(attr="a")
    var = hello::func("world")
end
""")

    assert len(statements) == 1
    assert len(statements[0].block.get_stmts()) == 2


def test_implementation_with_for():
    """Test the propagation of type requires when using a for
    """
    statements = parse_code("""
implementation test for Test:
    \"\"\" test \"\"\"
    for v in data:
        std::template("template")
    end
end
""")

    assert len(statements) == 1
    assert len(statements[0].block.get_stmts()) == 1


def test_implements():
    """Test implements with no selector
    """
    statements = parse_code("""
implement Test using test
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, DefineImplement)
    assert stmt.entity == "Test"
    assert stmt.implementations == ["test"]
    assert str(stmt.select) == "True"


def test_implements_2():
    """Test implements with selector
    """
    statements = parse_code("""
implement Test using test, blah when (self > 5)
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, DefineImplement)
    assert stmt.entity == "Test"
    assert stmt.implementations == ["test", "blah"]
    assert isinstance(stmt.select, GreaterThan)
    assert stmt.select.children[0].name == 'self'
    assert stmt.select.children[1].value == 5


def test_implements_Selector():
    """Test implements with selector
    """
    statements = parse_code("""
implement Test using test when not (fg(self) and false)
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, DefineImplement)
    assert stmt.entity == "Test"
    assert stmt.implementations == ["test"]
    assert isinstance(stmt.select, Not)
    assert isinstance(stmt.select.children[0], And)
    assert isinstance(stmt.select.children[0].children[0], FunctionCall)
    assert isinstance(stmt.select.children[0].children[1], Literal)


def test_regex():
    statements = parse_code("""
a = /[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}/
""")

    assert len(statements) == 1
    stmt = statements[0].value
    assert isinstance(stmt, Regex)
    assert stmt.children[1].value == re.compile(r"[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}")


def test_typedef():
    statements = parse_code("""
typedef uuid as string matching /[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}/
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, DefineTypeConstraint)
    assert stmt.name == "uuid"
    assert stmt.basetype == "string"
    assert isinstance(stmt.get_expression(), Regex)
    assert (stmt.get_expression().children[1].value ==
            re.compile(r"[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}"))


def test_typedef2():
    statements = parse_code("""
typedef ConfigFile as File(mode = 644, owner = "root", group = "root")
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, DefineTypeDefault)
    assert stmt.name == "ConfigFile"
    assert isinstance(stmt.ctor, Constructor)


def test_index():
    statements = parse_code("""
index File(host, path)
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, DefineIndex)
    assert stmt.type == "File"
    assert stmt.attributes == ["host", "path"]


def test_ctr():
    statements = parse_code("""
File(host = 5, path = "Jos")
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, Constructor)
    assert stmt.class_type == "File"
    assert {k: v.value for k, v in stmt.attributes.items()} == {"host": 5, "path": "Jos"}


def test_indexlookup():
    statements = parse_code("""
a=File[host = 5, path = "Jos"]
""")

    assert len(statements) == 1
    stmt = statements[0].value
    assert isinstance(stmt, IndexLookup)
    assert stmt.index_type == "File"
    assert {k: v.value for k, v in stmt.query} == {"host": 5, "path": "Jos"}


def test_ctr_2():
    statements = parse_code("""
File( )
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, Constructor)
    assert stmt.class_type == "File"
    assert {k: v.value for k, v in stmt.attributes.items()} == {}


def test_function():
    statements = parse_code("""
file( )
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, FunctionCall)
    assert stmt.name == "file"


def test_list_Def():
    statements = parse_code("""
a=["a]","b"]
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, Assign)
    assert isinstance(stmt.value, CreateList)
    assert [x.value for x in stmt.value.items] == ["a]", "b"]


def test_booleans():
    statements = parse_code("""
a=true b=false
""")

    assert len(statements) == 2
    stmt = statements[0]
    assert isinstance(stmt, Assign)
    assert stmt.value.value
    assert not statements[1].value.value


def test_Numbers():
    statements = parse_code("""
a=1
b=2.0
c=-5
d=-0.256
""")

    assert len(statements) == 4
    values = [1, 2.0, -5, -0.256]
    for i in range(4):
        stmt = statements[i]
        assert isinstance(stmt, Assign)
        assert stmt.value.value == values[i]


def test_StringFormat():
    statements = parse_code("""
a="j{{o}}s"
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, Assign)
    assert isinstance(stmt.value, StringFormat)
    assert isinstance(stmt.value._variables[0][0], Reference)
    assert [x[0].name for x in stmt.value._variables] == ["o"]


def test_StringFormat_2():
    statements = parse_code("""
a="j{{c.d}}s"
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, Assign)
    assert isinstance(stmt.value, StringFormat)
    assert len(stmt.value._variables) == 1
    assert len(stmt.value._variables[0]) == 2
    assert isinstance(stmt.value._variables[0][0], AttributeReference)
    assert stmt.value._variables[0][0].instance.name == "c"
    assert stmt.value._variables[0][0].attribute == "d"


def test_AttributeReference():
    statements = parse_code("""
a=a::b::c.d
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, Assign)
    assert isinstance(stmt.value, AttributeReference)
    assert isinstance(stmt.value.instance, Reference)
    assert stmt.value.instance.full_name == "a::b::c"
    assert stmt.value.attribute == "d"


def test_isDefined():
    statements = parse_code("""
implement Test1 using tt when self.other is defined
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, DefineImplement)
    assert isinstance(stmt.select, IsDefined)
    assert stmt.select.attr.name == 'self'
    assert stmt.select.name == 'other'


def test_isDefined_implicit_self():
    statements = parse_code("""
implement Test1 using tt when other is defined
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, DefineImplement)
    assert isinstance(stmt.select, IsDefined)
    assert stmt.select.attr.name == 'self'
    assert stmt.select.name == 'other'


def test_isDefined_short():
    statements = parse_code("""
implement Test1 using tt when a.other is defined
""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, DefineImplement)
    assert isinstance(stmt.select, IsDefined)
    assert isinstance(stmt.select.attr, AttributeReference)
    assert stmt.select.attr.instance.name == 'self'
    assert stmt.select.attr.attribute == 'a'
    assert stmt.select.name == 'other'


def test_defineListAttribute():
    statements = parse_code("""
entity Jos:
  bool[] bar
  ip::ip[] ips = ["a"]
  string[] floom = []
  string[] floomx = ["a", "b"]
end""")

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, DefineEntity)
    assert len(stmt.attributes) == 4

    def compareAttr(attr, name, type, defs):
        assert attr.name == name
        defs(attr.default)
        assert attr.multi
        assert attr.type == type

    def assert_is_none(x):
        assert x is None

    def assert_equals(x, y):
        assert x == y

    compareAttr(stmt.attributes[0], "bar", "bool", assert_is_none)
    compareAttr(stmt.attributes[2], "floom", "string", lambda x: assert_equals([], x.items))

    def compareDefault(list):
        def comp(x):
            assert len(list) == len(x.items)
            for one, it in zip(list, x.items):
                assert isinstance(it, Literal)
                assert it.value == one
        return comp
    compareAttr(stmt.attributes[1], "ips", "ip::ip", compareDefault(['a']))
    compareAttr(stmt.attributes[3], "floomx", "string", compareDefault(['a', 'b']))


def test_Lexer():
    parse_code("""
#test
//test2
a=0.5
b=""
""")


def test_Bad():
    with pytest.raises(ParserException):
        parse_code("""
a = b.c
a=a::b::c.
""")


def test_Bad2():
    with pytest.raises(ParserException):
        parse_code("""
a=|
""")
