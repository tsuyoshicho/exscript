# Copyright (C) 2007 Samuel Abels, http://debain.org
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
import copy, types

class Lexer(object):
    def __init__(self, parser_cls, *args, **kwargs):
        """
        The given args are passed to the parser_cls constructor.
        """
        self.parser_cls      = parser_cls
        self.parser_cls_args = args
        self.filename        = None
        self.input           = ''
        self.input_length    = 0
        self.current_char    = 0
        self.last_char       = 0
        self.token_buffer    = None
        self.grammar         = []
        self.debug           = kwargs.get('debug', False)

    def set_grammar(self, grammar):
        self.grammar.append(grammar)
        self.token_buffer = None

    def restore_grammar(self):
        self.grammar.pop()
        self.token_buffer = None

    def match(self):
        if self.current_char >= self.input_length:
            self.token_buffer = ('EOF', '')
            return
        for token_type, token_regex in self.grammar[-1]:
            match = token_regex.match(self.input, self.current_char)
            if match is not None:
                self.token_buffer = (token_type, match.group(0))
                #print "Match:", self.token_buffer
                return
        end   = self.input.find('\n', self.current_char + 2)
        error = 'Invalid syntax: %s' % repr(self.input[self.current_char:end])
        self.syntax_error(error)

    def _get_line_number_from_char(self, char):
        return self.input[:char].count('\n') + 1

    def _get_current_line_number(self):
        return self._get_line_number_from_char(self.current_char)

    def _get_line(self, number):
        return self.input.split('\n')[number - 1]

    def get_current_line(self):
        line = self._get_current_line_number()
        return self._get_line(line)

    def _get_line_from_char(self, char):
        line = self._get_line_number_from_char(char)
        return self._get_line(line)

    def _get_line_position_from_char(self, char):
        line_start = char
        while line_start != 0:
            if self.input[line_start - 1] == '\n':
                break
            line_start -= 1
        line_end = self.input.find('\n', char)
        return line_start, line_end

    def _error(self, error_type, error, sender = None):
        if not sender:
            raise Exception('\n' + error_type + ':\n' + error)
        start, end  = self._get_line_position_from_char(sender.end)
        line_number = self._get_line_number_from_char(sender.end)
        line        = self._get_line(line_number)
        offset      = sender.start - start
        token_len   = sender.end   - sender.start
        output      = line + '\n'
        if token_len <= 1:
            output += (' ' * offset) + '^\n'
        else:
            output += (' ' * offset) + "'" + ('-' * (token_len - 2)) + "'\n"
        output += '%s in %s:%s' % (error, self.filename, line_number)
        raise Exception('\n' + error_type + ':\n' + output)

    def syntax_error(self, error, sender = None):
        self._error('Syntax error', error, sender)

    def runtime_error(self, error, sender = None):
        self._error('Runtime error', error, sender)

    def forward(self, chars = 1):
        self.last_char     = self.current_char
        self.current_char += chars
        self.token_buffer  = None

    def next(self):
        if self.token_buffer:
            self.forward(len(self.token_buffer[1]))

    def next_if(self, types, token = None):
        if token is not None:
            if self.current_is(types, token):
                self.next()
                return 1
            return 0

        if type(types) != type([]):
            types = [types]
        for t in types:
            if self.current_is(t, token):
                self.next()
                return 1
        return 0

    def skip(self, types, token = None):
        while self.next_if(types, token):
            pass

    def expect(self, sender, type, token = None):
        cur_type, cur_token = self.token()
        if self.next_if(type, token):
            return
        if token:
            error = 'Expected "%s" but got %s %s'
            error = error % (token, cur_type, repr(cur_token))
        else:
            error = 'Expected %s but got %s (%s)'
            error = error % (type, cur_type, repr(cur_token))
        # In this case we do not point to the token that raised the error,
        # but to the actual position of the parser.
        sender.start = self.current_char
        sender.end   = self.current_char + 1
        self.syntax_error(error, sender)

    def current_is(self, type, token = None):
        if self.token_buffer is None:
            self.match()
        if self.token_buffer[0] != type:
            return 0
        if token is None:
            return 1
        if self.token_buffer[1] == token:
            return 1
        return 0

    def token(self):
        if self.token_buffer is None:
            self.match()
        return self.token_buffer

    def parse(self, string):
        # Re-initialize, so that the same parser instance may be used multiple
        # times.
        self.input        = string
        self.input_length = len(string)
        self.current_char = 0
        self.last_char    = 0
        self.token_buffer = None
        self.grammar      = []

        # Define the standard library now, in order to prevent it from being overwritten
        # by the user.
        compiled  = self.parser_cls(self, *self.parser_cls_args)
        if self.debug > 3:
            compiled.dump()
        return compiled

    def parse_file(self, filename):
        self.filename = filename
        fp            = open(filename)
        string        = fp.read()
        fp.close()
        return self.parse(string)