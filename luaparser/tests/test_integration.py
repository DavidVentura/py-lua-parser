from luaparser.utils import tests
from luaparser import ast
from luaparser.astnodes import *
import textwrap


class IntegrationTestCase(tests.TestCase):
    def test_cont_int_1(self):
        tree = ast.parse(textwrap.dedent(r'''
        describe("", function()
          it(function()
            do
              function foo()
              end
            end
          end)
          do
            function bar()
            end
          end
        end)
        '''))

        exp = Chunk(Block([
            Call(Name('describe'), [
                String('', StringDelimiter.DOUBLE_QUOTE),
                AnonymousFunction([], Block([
                    Call(Name('it'), [
                        AnonymousFunction([], Block([
                            Do(Block([
                                Function(Name('foo'), [], Block([]))
                            ]))
                        ]))
                    ]),
                    Do(Block([
                        Function(Name('bar'), [], Block([]))
                    ]))
                ]))
            ])
        ]))
        self.assertEqual(exp, tree)

    def test_cont_int_2(self):
        tree = ast.parse(textwrap.dedent(r'''
        if true then
          return true
        elseif isinstance() then
          return true
        end
        '''))

        exp = Chunk(Block([If(
            test=TrueExpr(),
            body=Block([Return([TrueExpr()])]),
            orelse=ElseIf(
                test=Call(Name('isinstance'), []),
                body=Block([Return([TrueExpr()])]),
                orelse=None
            )
        )]))
        self.assertEqual(exp, tree)

    # Unable to tell apart true indexing vs. syntactic sugar indexing #1
    def test_cont_int_3(self):
        tree = ast.parse(textwrap.dedent(r'x[a]'))
        exp = Chunk(Block([Index(idx=Name('a'), value=Name('x'), notation=IndexNotation.SQUARE)]))
        self.assertEqual(exp, tree)

        tree = ast.parse(textwrap.dedent(r'''x['a']'''))
        exp = Chunk(Block([Index(idx=String('a'), value=Name('x'), notation=IndexNotation.SQUARE)]))
        self.assertEqual(exp, tree)

        tree = ast.parse(textwrap.dedent(r'x.a'))
        exp = Chunk(Block([Index(idx=Name('a'), value=Name('x'))]))
        self.assertEqual(exp, tree)

    # luaparser.utils.visitor.VisitorException: No visitor found for class <enum 'StringDelimiter'> #11
    def test_cont_int_4(self):
        tree = ast.parse(textwrap.dedent(r'''
        local function sayHello()
            print('hello world !')
        end
        sayHello()
        '''))
        pretty_str = ast.to_pretty_str(tree)
        exp = textwrap.dedent(r'''
        Chunk: {} 5 keys
          start_char: 1
          stop_char: 67
          lineno: 2
          body: {} 5 keys
            Block: {} 5 keys
              start_char: 1
              stop_char: 67
              lineno: 2
              body: [] 2 items
                0: {} 1 key          
                  LocalFunction: {} 7 keys
                    start_char: 1
                    stop_char: 56
                    name: {} 5 keys
                      Name: {} 5 keys
                        start_char: 16
                        stop_char: 23
                        lineno: 2
                        id: 'sayHello'
                    args: [] 0 item
                    body: {} 5 keys
                      Block: {} 5 keys
                        start_char: 31
                        stop_char: 56
                        lineno: 3
                        body: [] 1 item
                          0: {} 1 key                    
                            Call: {} 6 keys
                              start_char: 31
                              stop_char: 52
                              lineno: 3
                              func: {} 5 keys
                                Name: {} 5 keys
                                  start_char: 31
                                  stop_char: 35
                                  lineno: 3
                                  id: 'print'
                              args: [] 1 item
                                0: {} 1 key                          
                                  String: {} 6 keys
                                    start_char: 37
                                    stop_char: 51
                                    lineno: 3
                                    s: 'hello world !'
                                    delimiter: SINGLE_QUOTE
                1: {} 1 key          
                  Call: {} 6 keys
                    start_char: 58
                    stop_char: 67
                    lineno: 5
                    func: {} 5 keys
                      Name: {} 5 keys
                        start_char: 58
                        stop_char: 65
                        lineno: 5
                        id: 'sayHello'
                    args: [] 0 item''')
        self.assertEqual(exp, pretty_str)
