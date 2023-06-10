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
    NUMBER    = auto()
    STRING    = auto()
    BOOL      = auto()
    FUNCTION  = auto()
    NULL      = auto()
    TABLE     = auto()
    TABLE_PTR = auto()
    UNKNOWN   = auto()
    UNK_PTR   = auto()

    def _repr(self):
        if self == Type.UNK_PTR:
            return 'TValue_t*'
        if self == Type.TABLE_PTR:
            return 'Table_t*'
        return 'TValue_t'

class Node:
    """Base class for AST node."""

    def replace_child(self, child, new_child):
        raise NotImplementedError(f'replace_child is not implemented for {type(self)}')

    def replace_child_multi(self, child, new_child):
        raise NotImplementedError(f'replace_child is not implemented for {type(self)}')

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
        if self.__class__ != other.__class__:
            return False
        return self._first_token == other._first_token and self._last_token == other._last_token

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

    def scope(self):
        if self.parent is None:
            return self

        if isinstance(self.parent, (Function, LocalFunction)):
            return self.parent

        return self.parent.scope()

    def is_inside(self, what):
        if self.parent is None:
            return None
        if isinstance(self.parent, what):
            return self.parent
        return self.parent.is_inside(what)


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
        raise ValueError(f'Expression dump not defined for {self.__class__}')



class Block(Node):
    """Define a Lua Block."""

    def __init__(self, body: List[Statement], **kwargs):
        super().__init__("Block", **kwargs)
        self.body: List[Statement] = body
        for s in body:
            s.parent = self
        self.functions: List[Function] = []
        self.vars: List = []

    def dump(self):
        return '\n'.join(s.dump() for s in self.body)

    def add_declaration(self, n: Node):
        self.body.insert(0, Declaration(n, Type.UNKNOWN))
        self.vars.append(n)

    def add_signatures(self, f: 'Function'):
        self.functions.append(f)
        self.body.insert(0, Signature(f))

    def replace_child(self, child, new_child):
        idx = self.body.index(child)
        self.body[idx] = new_child
        new_child.parent = self

    def replace_child_multi(self, child, new_children: list):
        if len(new_children) == 0:
            return
        idx = self.body.index(child)
        self.body[idx] = new_children[-1]
        self.body[idx].parent = self
        for new_child in new_children[:-1:-1]: # go backwards, skip the last child
            self.body.insert(idx, new_child)
            self.body[idx-1].parent = self


class Signature(Node):
    """Declares a function's signature."""
    def __init__(self, f: 'Function', **kwargs):
        super(Signature, self).__init__("Signature", **kwargs)
        self.f = f

    def dump(self):
        return f'{self.f.signature};'

class Declaration(Node):
    """Declares a variable with type"""
    def __init__(self, name: 'Name', type: Type, **kwargs):
        super(Declaration, self).__init__("Declaration", **kwargs)
        self.name = name
        self.type = type

    def dump(self):
        return f'{self.type._repr()} {self.name.id};'

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

    def add_declaration(self, n: Node):
        self.body.body.insert(0, Declaration(n, Type.UNKNOWN))


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

    def __init__(self, identifier: str, type=Type.UNKNOWN, **kwargs):
        super(Name, self).__init__("Name", **kwargs)
        self.id: str = identifier
        self.type = type

    def dump(self):
        return self.id


class IndexNotation(Enum):
    DOT = 0  # obj.foo
    SQUARE = 1  # obj[foo]

    def dump(self):
        return super().dump()


class ArrayIndex(Lhs):
    """
    Used to access subscripts through an index op after translating to an array:
    Given `TValue_t* arr = {...};`, this represents `arr[0]`
    """

    def __init__(
        self,
        idx: Expression,
        value: Name,
        **kwargs
    ):
        super(ArrayIndex, self).__init__("ArrayIndex", **kwargs)
        self.idx = idx
        self.value: Expression = value

    def dump(self):
        return f'{self.value.dump()}[{self.idx.dump()}]'

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
        self.idx = idx
        self.value: Expression = value
        self.notation: IndexNotation = notation
        if isinstance(idx, String):
            self.id = idx.s
        elif isinstance(idx, Number):
            self.id = idx.n
        else:
            self.id = idx.id
        self.value.type = Type.TABLE  # anything accessed via a lookup is a table
        self.optimized_access = False


    def dump_write(self, op: str, value: str):
        # a.t->set(FIELD___INDEX, a); // ?
        if isinstance(self.idx, String):
            _name = self.idx.s
        else:
            _name = self.idx.dump()
        field_name = f'FIELD_{_name.upper()}'
        return f'NOT_USED_set_tabvalue({self.value.dump()}.table, {field_name}, {value});'
        return f'{self.value.dump()}.table->{op}({field_name}, {value});'

    def dump(self):
        if self.optimized_access:
            if isinstance(self.idx, String):
                _name = self.idx.s
            else:
                _name = self.idx.dump()
            field_name = f'FIELD_{_name.upper()}'

            if isinstance(self.parent, Assign):
                assert False, "Should never call dump() on Index from Assign"
            return f'OPTIMIZEDget_tabvalue({self.value.dump()}, {field_name})'

        if isinstance(self.parent, Assign) and self in self.parent.targets:
            assert False, "This should've been replaced with SetTabValue"

        if self.notation == IndexNotation.DOT:
            # DOT notation (a.b) is always a string (a["b"])
            return f'get_tabvalue({self.value.dump()}.table, TSTR("{self.idx.dump()}"))'

        # bracket notation could be a string (a["b"])
        if isinstance(self.idx, String):
            return f'get_tabvalue({self.value.dump()}.table, {self.idx.dump()})'

        # a name (a[var]) or number (a[5])
        return f'get_tabvalue({self.value.dump()}.table, {self.idx.dump()})'

    @property
    def type(self):
        return self.value.type

""" ----------------------------------------------------------------------- """
""" Statements                                                              """
""" ----------------------------------------------------------------------- """


class SetTabValue(Statement):
    """
    Used to access set a table's key to a value
    """
    def __init__(self, table: Name, key: Expression, value: Expression, **kwargs):
        super().__init__("SetTabValue", **kwargs)
        self.table = table
        self.key = key
        self.value = value

    def dump(self):
        return f'set_tabvalue({self.table.dump()}.table, {self.key.dump()}, {self.value.dump()});'

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
        self.local: bool = False

        for t in self.targets:
            t.parent = self
        for v in self.values:
            v.parent = self

        # TODO a, b = c()
        assert len(self.targets) == len(self.values)

        for i in range(0, len(self.targets)):
            t = self.targets[i]
            v = self.values[i]

            if not isinstance(t, Index):
                if isinstance(v, Nil):
                    self.targets[i].type = Type.NULL
                if isinstance(v, Number):
                    self.targets[i].type = Type.NUMBER
                if isinstance(v, String):
                    self.targets[i].type = Type.STRING
                if isinstance(v, TrueExpr):
                    self.targets[i].type = Type.BOOL
                if isinstance(v, FalseExpr):
                    self.targets[i].type = Type.BOOL
                if isinstance(v, Table):
                    self.targets[i].type = Type.TABLE
                if isinstance(v, AnonymousFunction):
                    # TODO: closures (non top-level) should also be lambdas
                    self.targets[i].type = Type.FUNCTION
                if isinstance(v, Call):
                    self.targets[i].type = v.type

    def replace_child(self, child, new_child):
        new_child.parent = self
        for t in self.targets:
            if t == child:
                idx = self.targets.index(child)
                self.targets[idx] = new_child
        for v in self.values:
            if v == child:
                idx = self.values.index(child)
                self.values[idx] = new_child

    def dump(self):
        # TODO: multi assign
        assert len(self.targets) == len(self.values)
        r = []
        for i in range(0, len(self.targets)):
            t = self.targets[i]
            v = self.values[i]

            if isinstance(t, Index) and t.optimized_access:
                r.append(t.dump_write('set', v.dump()))
            elif t.type is Type.TABLE:
                r.append(f'{t.id} = {v.dump()};')
            elif t.type is Type.UNKNOWN:
                r.append(f'{t.dump()} = {v.dump()}; // ?')
            else:
                r.append(f'{t.dump()} = {v.dump()};')
        return '\n'.join(r)

class IAssign(Statement):
    def __init__(self, target: Node, value: Node, op: Expression, **kwargs):
        super().__init__("IAssign", **kwargs)
        self.target: Node = target
        self.value: Node = value
        self.op: Expression = op

        self.target.parent = self
        self.value.parent = self

    def dump(self):
        if isinstance(self.target, Index):
            # b.t->x += fix32(5)
            # ->
            # b.t->inc(FIELD_X, fix32(5));
            _map = {InplaceOp.ADD: 'inc',
                    InplaceOp.SUB: 'sub',
                    InplaceOp.MUL: 'mul',
                    InplaceOp.DIV: 'div',
                    }
            return  self.target.dump_write(_map[self.op], self.value.dump())

        _map = {InplaceOp.ADD:  '_pluseq',
                InplaceOp.SUB:  '_minuseq',
                InplaceOp.MUL: '_muleq',
                InplaceOp.DIV:  '_diveq',
                }
        return f'{_map[self.op]}(&{self.target.dump()}, {self.value.dump()});'



class LocalAssign(Assign):
    """Lua local assignment statement.

    Attributes:
        targets (`list<Node>`): List of targets.
        values (`list<Node>`): List of values.
    """

    def __init__(self, targets: List[Node], values: List[Node], **kwargs):
        super().__init__(targets, values, **kwargs)
        self._name: str = "LocalAssign"
        self.local: bool = True

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
        if isinstance(self.test, ULNotOp):
            _check = '!_bool'
        else:
            _check = '_bool'
        cond_arm = f'''
        if ({_check}({self.test.dump()})) {{
        {self.body.dump()}
        }}'''
        if isinstance(self.orelse, ElseIf):
            if isinstance(self.orelse.test, ULNotOp):
                _check = '!_bool'
            else:
                _check = '_bool'
            else_arm = f'''else if ({_check}({self.orelse.test.dump()})) {{
            {self.orelse.body.dump()}
            }}
            '''
        else:
            # no else arm
            if self.orelse is None or len(self.orelse.body) == 0:
                else_arm = ''
            else:
                stmts = '\n'.join(s.dump() for s in self.orelse.body)
                else_arm = f'''
                else {{
                    {stmts}
                }}'''
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
        for v in values:
            v.parent = self

        if len(values) == 0:
            self.type = Type.NULL

        if len(values) == 1:
            self.type = values[0].type

    def dump(self):
        if len(self.values) == 0:
            return 'return NULL;'

        if len(self.values) == 1:
            return f'return {self.values[0].dump()};'

        return f'return std::pair({", ".join(v.dump for v in self.values)});'


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
        return f'''for(TValue_t {self.target.dump()} = {self.start.dump()}; _lt({self.target.dump()}, {self.stop.dump()}); {self.target.dump()} = _add({self.target.dump()}, {self.step.dump()})) {{
            {NEWLINE.join(s.dump() for s in self.body.body)}
        }}'''


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

    def replace_child(self, child, new_child):
        idx = self.args.index(child)
        self.args[idx] = new_child
        new_child.parent = self

    def __init__(self, func: Expression, args: List[Expression], **kwargs):
        super(Call, self).__init__("Call", **kwargs)
        self.func: Expression = func
        self.args: List[Expression] = args
        self.type = Type.UNKNOWN
        # TODO propagate type information from func definition
        #if self.func and self.func.id == 'flr':
        #    self.type = Type.NUMBER

        if func:
            self.func.parent = self
        for a in self.args:
            a.parent = self

    def dump(self):
        # FIXME: finding "name in all scopes recursively going up" should be a thing
        is_vec = False
        if isinstance(self.scope().scope().body, Method):
            scope_ids = [n.id for n in self.scope().scope().vars]
        else:
            scope_ids = [n.id for n in self.scope().scope().body.vars]
        if self.func.id in scope_ids:
            is_vec = True
        if isinstance(self.func, Index): # table-based calls are always user-defined
            is_vec = True


        if is_vec:
            # bypass self
            args = f'{", ".join(a.dump() for a in self.args[1:])}'
            args = f'{self.args[0].dump()}, (TValue_t[]){{{args}}}'
        else:
            args = f'{", ".join(a.dump() for a in self.args)}'

        if isinstance(self.func, Index): # table-based calls are always user-defined
            r = f'''{self.func.dump()}.fun({args})'''
        else:
            r = f'''{self.func.dump()}({args})'''

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

    def replace_with_idx_call(self):
        i = Index(self.func, self.source)
        c = Call(i, [self.source]+self.args)
        return c

    def dump(self):
        raise ValueError("Must not call dump() on Invoke")


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

        for a in self.args:
            a.parent = self

        self.body.parent = self
        self.ret_type = '??'  # TODO - return + variable type analysis

        types = set()
        for expr in self.body.body:
            if isinstance(expr, Return):
                types.add(expr.type)

        if len(types) == 0:
            self.ret_type = Type.NULL
        if len(types) == 1:
            self.ret_type = types.pop()

    @property
    def signature(self):
        return f'{self.ret_type._repr()} {self.name.id}({", ".join(f"{a.type._repr()} " + a.dump() for a in self.args)})'

    def dump(self):
        return textwrap.dedent(f'''
         {self.signature} {{
            {NEWLINE.join(s.dump() for s in self.body.body)}
        }}''')

    def add_declaration(self, n: Node):
        self.body.body.insert(0, Declaration(n, Type.UNKNOWN))


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

        for a in self.args:
            a.parent = self

        self.vars = []
        self.body.parent = self
        self.ret_type = '??'  # TODO - return + variable type analysis

        types = set()
        for expr in self.body.body:
            if isinstance(expr, Return):
                types.add(expr.type)

        if len(types) == 0:
            self.ret_type = Type.NULL
        if len(types) == 1:
            self.ret_type = types.pop()

    def dump(self):
        raise ValueError('Should never call dump() on Method')

    def replace_with_function_and_assign(self):
        _args = [Name('self', type=Type.UNKNOWN), Name('function_arguments', type=Type.UNK_PTR)]
        f = Function(Name(f'__{self.source.id}_{self.name.id}'), _args, self.body)
        for arg in self.args:
            f.body.body.insert(0, Declaration(arg, Type.UNKNOWN));

        # after args declaration, assign the index value
        for (idx, arg) in enumerate(self.args):
            f.body.body.insert(len(self.args), Assign([arg], [ArrayIndex(Number(idx, ntype=NumberType.BARE_INT), Name('function_arguments'))]));

        a = SetTabValue(self.source, String(self.name.id), FunctionReference(f.name)) # Assign([i], [f.name])
        a.parent = self.parent
        return f, a


""" ----------------------------------------------------------------------- """
""" Lua Expression                                                          """
""" ----------------------------------------------------------------------- """

""" ----------------------------------------------------------------------- """
""" Types and values                                                        """
""" ----------------------------------------------------------------------- """


class Nil(Expression):
    """Define the Lua nil expression."""
    type = Type.NULL

    def __init__(self, **kwargs):
        super(Nil, self).__init__("Nil", **kwargs)

    def dump(self):
        return "T_NULL" # null tvalue


class TrueExpr(Expression):
    """Define the Lua true expression."""

    def __init__(self, **kwargs):
        super(TrueExpr, self).__init__("True", **kwargs)

    def dump(self):
        return 'T_TRUE'


class FalseExpr(Expression):
    """Define the Lua false expression."""

    def __init__(self, **kwargs):
        super(FalseExpr, self).__init__("False", **kwargs)

    def dump(self):
        return 'T_FALSE'


class NumberType(Enum):
    INT = auto()
    FLT = auto()
    FIX = auto()
    BARE_INT = auto()


class Number(Expression):
    """Define the Lua number expression.

    Attributes:
        n (`int|float`): Numeric value.
    """
    type = Type.NUMBER

    def __init__(self, n: str, ntype: NumberType, **kwargs):
        super(Number, self).__init__("Number", **kwargs)
        self.n: str = n
        self.ntype: NumberType = ntype

    def dump(self):
        # 0x77.aa -> fix32(0x77, 0xAA)
        if self.ntype is NumberType.FIX:
            _int, _dec = self.n.split('.')
            _dec = f'0x{_dec}'
            return f'TNUM(((fix32_t){{.i = {_int}, .f = {_dec} }}))'
        # 0.5 -> fix32(0.5f)
        if self.ntype is NumberType.FLT:
            return f'TNUM(fix32_from_float({self.n}f))'
        if self.ntype is NumberType.BARE_INT:
            return self.n

        # 1 -> fix32(1)
        return f'TNUM16({self.n})'


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


class FunctionReference(Expression):
    type = Type.FUNCTION
    def __init__(self, name: Name, **kwargs):
        super(FunctionReference, self).__init__("FunctionReference", **kwargs)
        self.name = name
    def dump(self):
        return f"TFUN({self.name.dump()})"

class String(Expression):
    """Define the Lua string expression.

    Attributes:
        s (`string`): String value.
        delimiter (`StringDelimiter`): The string delimiter
    """
    type = Type.STRING

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
        return f'TSTR("{self.s}")'


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
        if isinstance(self.key, (String, Number)):
            kd = self.key.dump()
        else:
            kd = f'TSTR("{self.key.dump()}")'
        return f'{kd}, {self.value.dump()}'


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
            # FIXME depends on context now; must be created in scope, then assigned at this point?
            _field_lines = []
            target_var = 'T_IDK'
            if isinstance(self.parent, Assign):
                target_var = self.parent.targets[0].id
                assert len(self.parent.targets) == 1, "Not sure which table this is"
            for f in self.fields:
                _field_lines.append(f'set_tabvalue({target_var}.table, {f.dump()});')
            _field_lines = "\n".join(_field_lines)
            return f'TTAB(make_table(4)); {_field_lines}'
        return 'TTAB(make_table(4))'


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
        for a in self.args:
            assert isinstance(a, Name)
        args = '\n'.join(f'TValue {a.id} = get_with_default(args, {idx});' for idx, a in enumerate(self.args))

        # Lift all closures to:
        # - Be declared as a regular, top-level function
        # - Read/Write _enclosed_ variables from UpValue table
        #   - How to know when it's an UpValue ???
        return f'''
        TValue([&](std::vector<TValue> args) -> TValue {{
            {args}
            {NEWLINE.join(s.dump() for s in self.body.body)}
        }})
    '''


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
        self.left.parent = self
        self.right.parent = self

    def dump(self):
        raise ValueError(f'BinaryOp not defined for {self.__class__}')


""" ----------------------------------------------------------------------- """
""" 3.4.1 – Arithmetic Operators                                            """
""" ----------------------------------------------------------------------- """


class AriOp(BinaryOp):
    """Base class for Arithmetic Operators"""
    type = Type.NUMBER


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
        return f'_div({self.left.dump()}, {self.right.dump()})'


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
        return f'({self.left.dump()} % {self.right.dump()})'


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
    type = Type.BOOL
    """Base class for Lua relational operators."""
    def dump(self):
        return f'{self.OP}({self.left.dump()}, {self.right.dump()})'


class LessThanOp(RelOp):
    """Less than expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """
    OP = '_lt'

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("RLtOp", left, right, **kwargs)


class GreaterThanOp(RelOp):
    """Greater than expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """
    OP = '_gt'

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("RGtOp", left, right, **kwargs)


class LessOrEqThanOp(RelOp):
    """Less or equal expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """
    OP = '_leq'

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("RLtEqOp", left, right, **kwargs)


class GreaterOrEqThanOp(RelOp):
    """Greater or equal expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """
    OP = '_geq'

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("RGtEqOp", left, right, **kwargs)


class EqToOp(RelOp):
    """Equal to expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """
    OP = '_equal'

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("REqOp", left, right, **kwargs)


class NotEqToOp(RelOp):
    """Not equal to expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """
    OP = '_notequal'

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("RNotEqOp", left, right, **kwargs)


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
        return f'_and({self.left.dump()}, {self.right.dump()})'


class OrLoOp(LoOp):
    """Logical or expression.

    Attributes:
        left (`Expression`): Left expression.
        right (`Expression`): Right expression.
    """

    def __init__(self, left: Expression, right: Expression, **kwargs):
        super().__init__("LOrOp", left, right, **kwargs)

    def dump(self):
        return f'_or({self.left.dump()}, {self.right.dump()})'


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
        self.operand.parent = self


class UMinusOp(UnaryOp):
    """Lua minus unitary operator.

    Attributes:
        operand (`Expression`): Operand.
    """

    def __init__(self, operand: Expression, **kwargs):
        super().__init__("UMinusOp", operand, **kwargs)

    def dump(self):
        return f'_invert_sign({self.operand.dump()})'


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
        return f'{self.operand.dump()}'


""" ----------------------------------------------------------------------- """
""" 3.4.7 – The Length Operator                                             """
""" ----------------------------------------------------------------------- """


class ULengthOP(UnaryOp):
    """Length operator."""

    def __init__(self, operand: Expression, **kwargs):
        super().__init__("ULengthOp", operand, **kwargs)

    def dump(self):
        return f'/* _length() */'
