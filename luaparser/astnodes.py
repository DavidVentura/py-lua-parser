"""
    ``astnodes`` module
    ===================

    Contains all Ast Node definitions.
"""
import textwrap
from enum import Enum, auto
from typing import List, Optional

from antlr4.Token import CommonToken

Comments = Optional[List["Comment"]]
NEWLINE = '\n'

class InplaceOp(Enum):
    ADD      = auto()
    SUB      = auto()
    MUL      = auto()
    DIV      = auto()

class Type(Enum):
    NUMBER   = auto()
    STRING   = auto()
    BOOL     = auto()
    FUNCTION = auto()
    NULL     = auto()
    TABLE    = auto()
    UNKNOWN  = auto()

def _equal_dicts(d1, d2, ignore_keys):
    ignored = set(ignore_keys)
    for k1, v1 in d1.items():
        if k1 not in ignored and (k1 not in d2 or d2[k1] != v1):
            return False
    for k2, v2 in d2.items():
        if k2 not in ignored and k2 not in d1:
            return False
    return True


class Node:
    """Base class for AST node."""

    def dump(self):
        raise NotImplementedError(f'dump is not implemented for {type(self)}')

    def __init__(
        self,
        name: str,
        comments: Comments = None,
        first_token: Optional[CommonToken] = None,
        last_token: Optional[CommonToken] = None,
        parent: Optional['Node'] = None,
    ):
        """

        Args:
            name: Node display name
            comments: Optional comments
            first_token: First Antlr token
            last_token: Last Antlr token
        """
        if comments is None:
            comments = []
        self._name: str = name
        self.comments: Comments = comments
        self._first_token: Optional[CommonToken] = first_token
        self._last_token: Optional[CommonToken] = last_token
        self.parent = parent

        # We want to have nodes be serializable with pickle.
        # To allow that we must not have mutable fields such as streams.
        # Tokens have streams, create a stream-less copy of tokens.
        if self._first_token is not None:
            self._first_token = self._first_token.clone()
            self._first_token.source = CommonToken.EMPTY_SOURCE

        if self._last_token is not None:
            self._last_token = self._last_token.clone()
            self._last_token.source = CommonToken.EMPTY_SOURCE

    @property
    def display_name(self) -> str:
        return self._name

    def __eq__(self, other) -> bool:
        if isinstance(self, other.__class__):
            return _equal_dicts(
                self.__dict__, other.__dict__, ["_first_token", "_last_token"]
            )
        return False

    @property
    def first_token(self) -> Optional[CommonToken]:
        """
        First token of a node.

        Note: Token is disconnected from underline source streams.
        """
        return self._first_token

    @first_token.setter
    def first_token(self, val: Optional[CommonToken]):
        if val is not None:
            self._first_token = val.clone()
            self._first_token.source = CommonToken.EMPTY_SOURCE

    @property
    def last_token(self) -> Optional[CommonToken]:
        """
        Last token of a node.

        Note: Token is disconnected from underline source streams.
        """
        return self._last_token

    @last_token.setter
    def last_token(self, val: Optional[CommonToken]):
        if val is not None:
            self._last_token = val.clone()
            self._last_token.source = CommonToken.EMPTY_SOURCE

    @property
    def start_char(self) -> Optional[int]:
        return self._first_token.start if self._first_token else None

    @property
    def stop_char(self) -> Optional[int]:
        return self._last_token.stop if self._last_token else None

    @property
    def line(self) -> Optional[int]:
        """Line number."""
        return self._first_token.line if self._first_token else None

    def to_json(self) -> any:
        return {
            self._name: {
                **{
                    k: v
                    for k, v in self.__dict__.items()
                    if not k.startswith("_") and v
                },
                **{
                    "start_char": self.start_char,
                    "stop_char": self.stop_char,
                    "line": self.line,
                },
            }
        }


class Comment(Node):
    def __init__(self, s: str, is_multi_line: bool = False, **kwargs):
        super().__init__("Comment", **kwargs)
        self.s: str = s
        self.is_multi_line: bool = is_multi_line

    def dump(self):
        pass


class Statement(Node):
    """Base class for Lua statement."""

    def dump(self):
        pass


class Expression(Node):
    """Define a Lua expression."""
    pass

    def dump(self):
        pass



class Block(Node):
    """Define a Lua Block."""

    def __init__(self, body: List[Statement], **kwargs):
        super().__init__("Block", **kwargs)
        self.body: List[Statement] = body
        for s in body:
            s.parent = self

    def dump(self):
        return '\n'.join(s.dump() for s in self.body)


class Chunk(Node):
    """Define a Lua chunk.

    Attributes:
        body (`Block`): Chunk body.
    """

    def __init__(self, body: Block, **kwargs):
        super(Chunk, self).__init__("Chunk", **kwargs)
        self.body = body
        body.parent = self

    def dump(self):
        pass


"""
Left Hand Side expression.
"""


class Lhs(Expression):
    """Define a Lua Left Hand Side expression."""

    def dump(self):
        return super().dump()


class Name(Lhs):
    """Define a Lua name expression.

    Attributes:
        id (`string`): Id.
    """

    def __init__(self, identifier: str, **kwargs):
        super(Name, self).__init__("Name", **kwargs)
        self.id: str = identifier

    def dump(self):
        return self.id


class IndexNotation(Enum):
    DOT = 0  # obj.foo
    SQUARE = 1  # obj[foo]

    def dump(self):
        return super().dump()


class Index(Lhs):
    """Define a Lua index expression.

    Attributes:
        idx (`Expression`): Index expression.
        value (`string`): Id.
    """

    def __init__(
        self,
        idx: Expression,
        value: Name,
        notation: IndexNotation = IndexNotation.DOT,
        **kwargs
    ):
        super(Index, self).__init__("Index", **kwargs)
        self.idx: Name = idx
        self.value: Expression = value
        self.notation: IndexNotation = notation
        self.id = idx.id


    def dump(self):
        if self.notation == IndexNotation.DOT:
            return f'{self.value.dump()}.t["{self.idx.dump()}"]'
        if isinstance(self.idx, String):
            return f'{self.value.dump()}.t["{self.idx.dump()}"]'
        return f'{self.value.dump()}.t[{self.idx.dump()}]'

""" ----------------------------------------------------------------------- """
""" Statements                                                              """
""" ----------------------------------------------------------------------- """


class Assign(Statement):
    """Lua global assignment statement.

    Attributes:
        targets (`list<Node>`): List of targets.
        values (`list<Node>`): List of values.

    """

    def __init__(self, targets: List[Node], values: List[Node], **kwargs):
        super().__init__("Assign", **kwargs)
        self.targets: List[Node] = targets
        self.values: List[Node] = values
        # TODO: actually go up to chunk
        # look up for variables with name T and assign their type there
        # so that other things like `AddOp` can do the same
        # and emit `+` for known types
        self.type = Type.UNKNOWN

        assert len(self.targets) == 1
        assert len(self.values) == 1
        t = self.targets[0]
        v = self.values[0]

        if isinstance(v, Number):
            self.type = Type.NUMBER
        if isinstance(v, String):
            self.type = Type.STRING
        if isinstance(v, TrueExpr):
            self.type = Type.BOOL
        if isinstance(v, FalseExpr):
            self.type = Type.BOOL
        if isinstance(v, Table):
            self.type = Type.TABLE

    def dump(self):
        # TODO: multi assign
        assert len(self.targets) == 1
        assert len(self.values) == 1
        t = self.targets[0]
        v = self.values[0]
        
        if self.type == Type.NUMBER:
            r = f'{t.dump()} = TVfromnumber({v.dump()});'
        elif self.type == Type.STRING:
            r = f'{t.dump()} = TVfromstr({v.dump()});'
        elif self.type == Type.STRING:
            r = f'{t.dump()} = TVfromstr({v.dump()});'
        elif self.type == Type.BOOL:
            r = f'{t.dump()} = TVfromnumber({v.dump()}); // bool'
        elif self.type == Type.UNKNOWN:
            r = f'{t.dump()} = {v.dump()}; // unknown'
        elif self.type == Type.TABLE:
            r = f'std::unordered_map<std::string, TValue>{t.id} = {v.dump()};'
        else:
            raise ValueError(f'Assignment on type {self.type} unsupported')
        return r

class IAssign(Statement):
    def __init__(self, target: Node, value: Node, op: Expression, **kwargs):
        super().__init__("IAssign", **kwargs)
        self.target: Node = target
        self.value: Node = value
        self.op: Expression = op

        self.target.parent = self
        self.value.parent = self

    def dump(self):
        _map = {InplaceOp.ADD:  '+=',
                InplaceOp.SUB:  '-=',
                InplaceOp.MUL: '*=',
                InplaceOp.DIV:  '/=',
                }
        return f'{self.target.dump()} {_map[self.op]} {self.value.dump()};'



class LocalAssign(Assign):
    """Lua local assignment statement.

    Attributes:
        targets (`list<Node>`): List of targets.
        values (`list<Node>`): List of values.
    """

    def __init__(self, targets: List[Node], values: List[Node], **kwargs):
        super().__init__(targets, values, **kwargs)
        self._name: str = "LocalAssign"

    def dump(self):
        return super().dump()


class While(Statement):
    """Lua while statement.

    Attributes:
        test (`Node`): Expression to test.
        body (`Block`): List of statements to execute.
    """

    def __init__(self, test: Expression, body: Block, **kwargs):
        super().__init__("While", **kwargs)
        self.test: Expression = test
        self.body: Block = body
        self.test.parent = self
        self.body.parent = self

    def dump(self):
        return super().dump()


class Do(Statement):
    """Lua do end statement.

    Attributes:
        body (`Block`): List of statements to execute.
    """

    def __init__(self, body: Block, **kwargs):
        super().__init__("Do", **kwargs)
        self.body: Block = body
        self.body.parent = self

    def dump(self):
        return super().dump()


class Repeat(Statement):
    """Lua repeat until statement.

    Attributes:
        test (`Node`): Expression to test.
        body (`Block`): List of statements to execute.
    """

    def __init__(self, body: Block, test: Expression, **kwargs):
        super().__init__("Repeat", **kwargs)
        self.body: Block = body
        self.test: Expression = test
        self.body.parent = self
        self.test.parent = self

    def dump(self):
        return super().dump()


class ElseIf(Statement):
    """Define the elseif lua statement.

    Attributes:
        test (`Node`): Expression to test.
        body (`list<Statement>`): List of statements to execute if test is true.
        orelse (`list<Statement> or ElseIf`): List of statements or ElseIf if test if false.
    """

    def __init__(self, test: Node, body: Block, orelse, **kwargs):
        super().__init__("ElseIf", **kwargs)
        self.test: Node = test
        self.body: Block = body
        self.orelse = orelse

        self.test.parent = self
        self.body.parent = self
        if orelse:
            self.orelse.parent = self

    def dump(self):
        return super().dump()


class If(Statement):
    """Lua if statement.

    Attributes:
        test (`Node`): Expression to test.
        body (`Block`): List of statements to execute if test is true.
        orelse (`list<Statement> or ElseIf`): List of statements or ElseIf if test if false.
    """

    def __init__(
        self, test: Expression, body: Block, orelse: List[Statement] or ElseIf, **kwargs
    ):
        super().__init__("If", **kwargs)
        self.test: Expression = test
        self.body: Block = body
        self.orelse = orelse

        self.test.parent = self
        self.body.parent = self
        if orelse:
            self.orelse.parent = self

    def dump(self):
        cond_arm = f'''
        if ({self.test.dump()}) {{
        {self.body.dump()}
        }}'''
        if isinstance(self.orelse, ElseIf):
            else_arm = f'''else if ({self.orelse.test.dump()}) {{
            {self.orelse.body.dump()}
            }}
            '''
        else:
            # no else arm
            if self.orelse is None or len(self.orelse) == 0:
                else_arm = ''
            else:
                else_arm = '\n'.join(s.dump() for s in self.orelse)
        return cond_arm + else_arm


class Label(Statement):
    """Define the label lua statement.

    Attributes:
        id (`Name`): Label name.
    """

    def __init__(self, label_id: Name, **kwargs):
        super(Label, self).__init__("Label", **kwargs)
        self.id: Name = label_id

    def dump(self):
        return super().dump()


class Goto(Statement):
    """Define the goto lua statement.

    Attributes:
        label (`Name`): Label node.
    """

    def __init__(self, label: Name, **kwargs):
        super(Goto, self).__init__("Goto", **kwargs)
        self.label: Name = label

    def dump(self):
        return super().dump()


class SemiColon(Statement):
    """Define the semi-colon lua statement."""

    def __init__(self, **kwargs):
        super(SemiColon, self).__init__("SemiColon", **kwargs)

    def dump(self):
        return super().dump()


class Break(Statement):
    """Define the break lua statement."""

    def __init__(self, **kwargs):
        super(Break, self).__init__("Break", **kwargs)

    def dump(self):
        return super().dump()


class Return(Statement):
    """Define the Lua return statement.

    Attributes:
        values (`list<Expression>`): Values to return.
    """

    def __init__(self, values, **kwargs):
        super(Return, self).__init__("Return", **kwargs)
        self.values = values
        self.values.parent = self

    def dump(self):
        return super().dump()


class Fornum(Statement):
    """Define the numeric for lua statement.

    Attributes:
        target (`Name`): Target name.
        start (`Expression`): Start index value.
        stop (`Expression`): Stop index value.
        step (`Expression`): Step value.
        body (`Block`): List of statements to execute.
    """

    def __init__(
        self,
        target: Name,
        start: Expression,
        stop: Expression,
        step: Expression,
        body: Block,
        **kwargs
    ):
        super(Fornum, self).__init__("Fornum", **kwargs)
        self.target: Name = target
        self.start: Expression = start
        self.stop: Expression = stop
        self.step: Expression = step
        self.body: Block = body

        self.target.parent = self
        self.start.parent = self
        self.stop.parent = self
        self.step.parent = self
        self.body.parent = self

    def dump(self):
        return super().dump()


class Forin(Statement):
    """Define the for in lua statement.

    Attributes:
        body (`Block`): List of statements to execute.
        iter (`list<Expression>`): Iterable expressions.
        targets (`list<Name>`): Start index value.
    """

    def __init__(
        self, body: Block, iter: List[Expression], targets: List[Name], **kwargs
    ):
        super(Forin, self).__init__("Forin", **kwargs)
        self.body: Block = body
        self.iter: List[Expression] = iter
        self.targets: List[Name] = targets

        self.body.parent = self
        for i in self.iter:
            i.parent = self
        for t in self.targets:
            t.parent = self

    def dump(self):
        return super().dump()


class Call(Statement):
    """Define the function call lua statement.

    Attributes:
        func (`Expression`): Function to call.
        args (`list<Expression>`): Function call arguments.
    """

    def __init__(self, func: Expression, args: List[Expression], **kwargs):
        super(Call, self).__init__("Call", **kwargs)
        self.func: Expression = func
        self.args: List[Expression] = args

        if func:
            self.func.parent = self
        for a in self.args:
            a.parent = self

    def dump(self):
        r = f'''{self.func.id}({", ".join(a.dump() for a in self.args)})'''
        if isinstance(self.parent, Block):
            r += ';'
        return r


class Invoke(Statement):
    """Define the invoke function call lua statement (magic syntax with ':').

    Attributes:
        source (`Expression`): Source expression where function is invoked.
        func (`Expression`): Function to call.
        args (`list<Expression>`): Function call arguments.
    """

    def __init__(
        self, source: Expression, func: Expression, args: List[Expression], **kwargs
    ):
        super(Invoke, self).__init__("Invoke", **kwargs)
        self.source: Expression = source
        self.func: Expression = func
        self.args: List[Expression] = args

    def dump(self):
        return super().dump()


class Function(Statement):
    """Define the Lua function declaration statement.

    Attributes:
        name (`Expression`): Function name.
        args (`list<Expression>`): Function arguments.
        body (`Block`): List of statements to execute.
    """

    def __init__(self, name: Expression, args: List[Expression], body: Block, **kwargs):
        super(Function, self).__init__("Function", **kwargs)
        self.name: Expression = name
        self.args: List[Expression] = args
        self.body: Block = body

    def dump(self):
        return textwrap.dedent(f'''
        TValue* {self.name.id}({", ".join("TValue " + a.dump() for a in self.args)}) {{
            {NEWLINE.join(s.dump() for s in self.body.body)}
            return NULL;
        }}''')


class LocalFunction(Function):
    """Define the Lua local function declaration statement.

    Attributes:
        name (`Expression`): Function name.
        args (`list<Expression>`): Function arguments.
        body (`list<Statement>`): List of statements to execute.
    """

    def __init__(self, name: Expression, args: List[Expression], body: Block, **kwargs):
        super(LocalFunction, self).__init__("LocalFunction", **kwargs)
        self.name: Expression = name
        self.args: List[Expression] = args
        self.body: Block = body

    def dump(self):
        return super().dump()


class Method(Statement):
    """Define the Lua Object Oriented function statement.

    Attributes:
        source (`Expression`): Source expression where method is defined.
        name (`Expression`): Function name.
        args (`list<Expression>`): Function arguments.
        body (`Block`): List of statements to execute.
    """

    def __init__(
        self,
        source: Expression,
        name: Expression,
        args: List[Expression],
        body: Block,
        **kwargs
    ):
        super(Method, self).__init__("Method", **kwargs)
        self.source: Expression = source
        self.name: Expression = name
        self.args: List[Expression] = args
        self.body: Block = body

    def dump(self):
        return super().dump()


""" ----------------------------------------------------------------------- """
""" Lua Expression                                                          """
""" ----------------------------------------------------------------------- """

""" ----------------------------------------------------------------------- """
""" Types and values                                                        """
""" ----------------------------------------------------------------------- """


class Nil(Expression):
    """Define the Lua nil expression."""

    def __init__(self, **kwargs):
        super(Nil, self).__init__("Nil", **kwargs)

    def dump(self):
        return super().dump()


class TrueExpr(Expression):
    """Define the Lua true expression."""

    def __init__(self, **kwargs):
        super(TrueExpr, self).__init__("True", **kwargs)

    def dump(self):
        return 'true'


class FalseExpr(Expression):
    """Define the Lua false expression."""

    def __init__(self, **kwargs):
        super(FalseExpr, self).__init__("False", **kwargs)

    def dump(self):
        return 'false'


NumberType = int or float


class Number(Expression):
    """Define the Lua number expression.

    Attributes:
        n (`int|float`): Numeric value.
    """

    def __init__(self, n: NumberType, **kwargs):
        super(Number, self).__init__("Number", **kwargs)
        self.n: NumberType = n

    def dump(self):
        return str(self.n)


class Varargs(Expression):
    """Define the Lua Varargs expression (...)."""

    def __init__(self, **kwargs):
        super(Varargs, self).__init__("Varargs", **kwargs)

    def dump(self):
        return super().dump()


class StringDelimiter(Enum):
    SINGLE_QUOTE = 0  # 'foo'
    DOUBLE_QUOTE = 1  # "foo"
    DOUBLE_SQUARE = 2  # [[foo]]


class String(Expression):
    """Define the Lua string expression.

    Attributes:
        s (`string`): String value.
        delimiter (`StringDelimiter`): The string delimiter
    """

    def __init__(
        self,
        s: str,
        delimiter: StringDelimiter = StringDelimiter.SINGLE_QUOTE,
        **kwargs
    ):
        super(String, self).__init__("String", **kwargs)
        self.s: str = s
        self.delimiter: StringDelimiter = delimiter

    def dump(self):
        return f'"{self.s}"'


class Field(Expression):
    """Define a lua table field expression

    Attributes:
        key (`Expression`): Key.
        value (`Expression`): Value.
    """

    def __init__(
        self,
        key: Expression,
        value: Expression,
        between_brackets: bool = False,
        **kwargs
    ):
        super().__init__("Field", **kwargs)
        self.key: Expression = key
        self.value: Expression = value
        self.between_brackets: bool = between_brackets

    def dump(self):
        return f'{{ "{self.key.dump()}", {self.value.dump()} }}'


class Table(Expression):
    """Define the Lua table expression.

    Attributes:
        fields (`list<Field>`): Table fields.
    """

    def __init__(self, fields: List[Field], **kwargs):
        super().__init__("Table", **kwargs)
        self.fields: List[Field] = fields


    def dump(self):
        if self.fields:
            return f'{{ {", ".join(f.dump() for f in self.fields)} }}'
        return '{}'


class Dots(Expression):
    """Define the Lua dots (...) expression."""

    def __init__(self, **kwargs):
        super().__init__("Dots", **kwargs)

    def dump(self):
        return super().dump()


class AnonymousFunction(Expression):
    """Define the Lua anonymous function expression.

    Attributes:
        args (`list<Expression>`): Function arguments.
        body (`Block`): List of statements to execute.
    """

    def __init__(self, args: List[Expression], body: Block, **kwargs):
        super(AnonymousFunction, self).__init__("AnonymousFunction", **kwargs)
        self.args: List[Expression] = args
        self.body: Block = body

    def dump(self):
        return super().dump()


""" ----------------------------------------------------------------------- """
""" Operators                                                               """
""" ----------------------------------------------------------------------- """


class Op(Expression):
    """Base class for Lua operators."""


class BinaryOp(Op):
    """Base class for Lua 'Left Op Right' Operators.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, name, left: Expression, right: Expression, **kwargs):
        super(BinaryOp, self).__init__(name, **kwargs)
        self.left: Expression = left
        self.right: Expression = right

    def dump(self):
        return super().dump()


""" ----------------------------------------------------------------------- """
""" 3.4.1 – Arithmetic Operators                                            """
""" ----------------------------------------------------------------------- """


class AriOp(BinaryOp):
    """Base class for Arithmetic Operators"""


class AddOp(AriOp):
    """Add expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("AddOp", left, right, **kwargs)

    def dump(self):
        return f'_add({self.left.dump()}, {self.right.dump()})'


class SubOp(AriOp):
    """Substract expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("SubOp", left, right, **kwargs)

    def dump(self):
        return f'_sub({self.left.dump()}, {self.right.dump()})'


class MultOp(AriOp):
    """Multiplication expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("MultOp", left, right, **kwargs)

    def dump(self):
        return f'_mult({self.left.dump()}, {self.right.dump()})'


class FloatDivOp(AriOp):
    """Float division expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("FloatDivOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


class FloorDivOp(AriOp):
    """Floor division expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("FloorDivOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


class ModOp(AriOp):
    """Modulo expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("ModOp", left, right, **kwargs)

    def dump(self):
        return f'{self.left.dump()} % {self.right.dump()}'


class ExpoOp(AriOp):
    """Exponent expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("ExpoOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


""" ----------------------------------------------------------------------- """
""" 3.4.2 – Bitwise Operators                                               """
""" ----------------------------------------------------------------------- """


class BitOp(BinaryOp):
    """Base class for bitwise Operators."""


class BAndOp(BitOp):
    """Bitwise and expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("BAndOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


class BOrOp(BitOp):
    """Bitwise or expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("BOrOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


class BXorOp(BitOp):
    """Bitwise xor expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("BXorOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


class BShiftROp(BitOp):
    """Bitwise right shift expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("BShiftROp", left, right, **kwargs)

    def dump(self):
        return super().dump()


class BShiftLOp(BitOp):
    """Bitwise left shift expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("BShiftLOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


""" ----------------------------------------------------------------------- """
""" 3.4.4 – Relational Operators                                            """
""" ----------------------------------------------------------------------- """


class RelOp(BinaryOp):
    """Base class for Lua relational operators."""
    def dump(self):
        return f'({self.left.dump()} {self.OP} {self.right.dump()})'


class LessThanOp(RelOp):
    """Less than expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """
    OP = '<'

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("RLtOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


class GreaterThanOp(RelOp):
    """Greater than expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """
    OP = '>'

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("RGtOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


class LessOrEqThanOp(RelOp):
    """Less or equal expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """
    OP = '<='

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("RLtEqOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


class GreaterOrEqThanOp(RelOp):
    """Greater or equal expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """
    OP = '>='

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("RGtEqOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


class EqToOp(RelOp):
    """Equal to expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """
    OP = '=='

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("REqOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


class NotEqToOp(RelOp):
    """Not equal to expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """
    OP = '!='

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("RNotEqOp", left, right, **kwargs)

    def dump(self):
        return super().dump()


""" ----------------------------------------------------------------------- """
""" 3.4.5 – Logical Operators                                               """
""" ----------------------------------------------------------------------- """


class LoOp(BinaryOp):
    """Base class for logical operators."""


class AndLoOp(LoOp):
    """Logical and expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("LAndOp", left, right, **kwargs)

    def dump(self):
        return f'({self.left.dump()} && {self.right.dump()})'


class OrLoOp(LoOp):
    """Logical or expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("LOrOp", left, right, **kwargs)

    def dump(self):
        return f'({self.left.dump()} || {self.right.dump()})'


""" ----------------------------------------------------------------------- """
""" 3.4.6 Concat operators                                                  """
""" ----------------------------------------------------------------------- """


class Concat(BinaryOp):
    """Concat expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("Concat", left, right, **kwargs)

    def dump(self):
        return f'_concat({self.left.dump()}, {self.right.dump()})'


""" ----------------------------------------------------------------------- """
""" Unary operators                                                         """
""" ----------------------------------------------------------------------- """


class UnaryOp(Expression):
    """Base class for Lua unitary operator.

    Attributes:
        operand (`Expression`): Operand.
    """

    def __init__(self, name: str, operand: Expression, **kwargs):
        super().__init__(name, **kwargs)
        self.operand = operand

    def dump(self):
        return super().dump()


class UMinusOp(UnaryOp):
    """Lua minus unitary operator.

    Attributes:
        operand (`Expression`): Operand.
    """

    def __init__(self, operand: Expression, **kwargs):
        super().__init__("UMinusOp", operand, **kwargs)

    def dump(self):
        return f'-{self.operand.dump()}'


class UBNotOp(UnaryOp):
    """Lua binary not unitary operator.

    Attributes:
        operand (`Expression`): Operand.
    """

    def __init__(self, operand: Expression, **kwargs):
        super().__init__("UBNotOp", operand, **kwargs)

    def dump(self):
        return f'~{self.operand.dump()}'


class ULNotOp(UnaryOp):
    """Logical not operator.

    Attributes:
        operand (`Expression`): Operand.
    """

    def __init__(self, operand: Expression, **kwargs):
        super().__init__("ULNotOp", operand, **kwargs)

    def dump(self):
        return f'!{self.operand.dump()}'


""" ----------------------------------------------------------------------- """
""" 3.4.7 – The Length Operator                                             """
""" ----------------------------------------------------------------------- """


class ULengthOP(UnaryOp):
    """Length operator."""

    def __init__(self, operand: Expression, **kwargs):
        super().__init__("ULengthOp", operand, **kwargs)

    def dump(self):
        return f'_length({operand})'
