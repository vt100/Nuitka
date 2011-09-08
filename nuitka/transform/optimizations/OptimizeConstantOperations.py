#
#     Copyright 2011, Kay Hayen, mailto:kayhayen@gmx.de
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     If you submit Kay Hayen patches to this software in either form, you
#     automatically grant him a copyright assignment to the code, or in the
#     alternative a BSD license to the code, should your jurisdiction prevent
#     this. Obviously it won't affect code that comes to him indirectly or
#     code you don't submit to him.
#
#     This is to reserve my ability to re-license the code at any time, e.g.
#     the PSF. With this version of Nuitka, using it for Closed Source will
#     not be allowed.
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, version 3 of the License.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#     Please leave the whole of this copyright notice intact.
#
""" Optimize operations on constant nodes.

"""

from .OptimizeBase import OptimizationVisitorBase, areConstants

from nuitka import Nodes

class OptimizeOperationVisitor( OptimizationVisitorBase ):
    def _optimizeConstantOperandsOperation( self, node, operands ):
        operands = [ constant.getConstant() for constant in operands ]

        def simulate():
            # This is a convinent way to execute no matter what the number of
            # operands is. pylint: disable=W0142
            return node.getSimulator()( *operands )

        self.replaceWithComputationResult(
            node        = node,
            computation = simulate,
            description = "Operation with constant args"
        )

    def _optimizeConstantOperandsComparison( self, node ):
        comparators = node.getComparators()

        # TODO: Handle cases with multiple comparators too.
        if len( comparators ) != 1:
            return

        operand1, operand2 = node.getOperands()

        if areConstants( ( operand1, operand2 ) ):
            value1 = operand1.getConstant()
            value2 = operand2.getConstant()

            simulator = node.getSimulator( 0 )

            def simulate():
                return simulator( value1, value2 )

            self.replaceWithComputationResult(
                node        = node,
                computation = simulate,
                description = "Comparison with constant args"
            )

    def _optimizeConstantConditionalOperation( self, node ):
        condition = node.getCondition()

        if condition.isExpressionConstantRef():
            if condition.getConstant():
                choice = "true"

                new_node = node.getBranchYes()
            else:
                choice = "false"

                new_node = node.getBranchNo()

            if new_node is None:
                new_node = Nodes.CPythonStatementPass(
                    source_ref = node.getSourceReference()
                )

            node.replaceWith( new_node )

            self.signalChange(
                "new_statements",
                node.getSourceReference(),
                "Condition for branch was predicted to be always %s." % choice
            )
        else:
            no_branch = node.getBranchNo()

            if no_branch is not None and not no_branch.mayHaveSideEffects():
                no_branch = None

                node.setBranchNo( None )

            yes_branch = node.getBranchYes()

            if yes_branch is not None and not yes_branch.mayHaveSideEffects():
                yes_branch = None

                node.setBranchYes( None )

            if no_branch is None and yes_branch is None:
                new_node = Nodes.CPythonStatementExpressionOnly(
                    expression = node.getCondition(),
                    source_ref = node.getSourceReference()
                )

                node.replaceWith( new_node )

                self.signalChange(
                    "new_statements",
                    node.getSourceReference(),
                    "Both branches have no effect, drop conditional."
                )

    def _optimizeForLoop( self, node ):
        no_break = node.getNoBreak()

        if no_break is not None and not no_break.mayHaveSideEffects():
            no_break = None

            node.setNoBreak( None )

        body = node.getBody()

        if body is not None and not body.mayHaveSideEffects():
            body = None

            node.setBody( None )

        # TODO: Optimize away the for loop if possible, if e.g. the iteration has
        # no side effects, it's result is predictable etc.

    def __call__( self, node ):
        if node.isOperation():
            operands = node.getOperands()

            if areConstants( operands ):
                self._optimizeConstantOperandsOperation(
                    node     = node,
                    operands = operands
                )
        elif node.isExpressionComparison():
            self._optimizeConstantOperandsComparison(
                node = node
            )
        elif node.isStatementConditional():
            self._optimizeConstantConditionalOperation(
                node = node
            )
        # TODO: Move this to a separate optimization step.
        elif node.isStatementForLoop():
            self._optimizeForLoop(
                node = node
            )
        # TODO: Move this to a separate optimization step.
        elif node.isExpressionFunctionCall():
            star_list_arg = node.getStarListArg()

            if star_list_arg is not None:
                if star_list_arg.isExpressionMakeSequence():
                    positional_args = node.getPositionalArguments()

                    node.setPositionalArguments( positional_args + star_list_arg.getElements() )
                    node.setStarListArg( None )
                elif star_list_arg.isExpressionConstantRef():
                    if star_list_arg.isIterableConstant():
                        positional_args = node.getPositionalArguments()

                        constant_nodes = []

                        for constant in star_list_arg.getConstant():
                            constant_nodes.append(
                                Nodes.makeConstantReplacementNode(
                                    constant = constant,
                                    node     = star_list_arg
                                )
                            )

                        node.setPositionalArguments( positional_args + tuple( constant_nodes ) )
                        node.setStarListArg( None )


            star_dict_arg = node.getStarDictArg()

            if star_dict_arg is not None:
                if star_dict_arg.isExpressionMakeDict():
                    # TODO: Need to cleanup the named argument mess before it is possible.
                    pass
                elif star_dict_arg.isExpressionConstantRef():
                    # TODO: Need to cleanup the named argument mess before it is possible.
                    pass