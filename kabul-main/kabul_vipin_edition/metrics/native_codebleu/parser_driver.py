# -*- coding: utf-8 -*-
"""
Tree-sitter Parser Driver for C#
Handles parser initialization and tree parsing using the new tree-sitter API.
"""

import tree_sitter
import tree_sitter_c_sharp

class CSharpParser:
    _instance = None
    _parser = None
    _language = None

    @classmethod
    def get_parser(cls):
        if cls._parser is None:
            try:
                # Tree-sitter 0.22+ initialization
                cls._language = tree_sitter.Language(tree_sitter_c_sharp.language(), "c_sharp")
                cls._parser = tree_sitter.Parser()
                cls._parser.set_language(cls._language)
            except TypeError:
                # Fallback or alternate init if needed
                cls._language = tree_sitter_c_sharp.language()
                cls._parser = tree_sitter.Parser()
                cls._parser.set_language(cls._language)
                
        return cls._parser
    
    @classmethod
    def parse(cls, code: bytes):
        parser = cls.get_parser()
        return parser.parse(code)

    @classmethod
    def get_language(cls):
        if cls._language is None:
            cls.get_parser()
        return cls._language
