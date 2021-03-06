#!/usr/bin/python -B

from string import Template, upper, replace

from ApiUtil import outputCode
from ApiUtil import typeIsVoid

from ApiCodeGen import *

from RegalDispatchShared import dispatchSourceTemplate
from RegalDispatchLog import apiDispatchFuncInitCode
from RegalDispatchEmu import dispatchSourceTemplate
from RegalContextInfo import cond

##############################################################################################

def apiDispatchTableDefineCode(apis, args, apiNames, structName):
  code = '''
  struct %s
  {
    inline void setFunction(const size_t offset, void *func)
    {
      RegalAssert((offset*sizeof(void *))<sizeof(this));
      ((void **)(this))[offset] = func;
    }
'''%(structName)

  for api in apis:

    if not api.name in apiNames:
      continue

    code += '\n'
    if api.name in cond:
      code += '#if %s\n' % cond[api.name]

    categoryPrev = None

    for function in api.functions:

      if getattr(function,'regalOnly',False)==True:
        continue

      name   = function.name
      params = paramsDefaultCode(function.parameters, True)
      rType  = typeCode(function.ret.type)
      category  = getattr(function, 'category', None)
      version   = getattr(function, 'version', None)

      if category:
        category = category.replace('_DEPRECATED', '')
      elif version:
        category = version.replace('.', '_')
        category = 'GL_VERSION_' + category

      # Close prev if block.
      if categoryPrev and not (category == categoryPrev):
        code += '\n'

      # Begin new if block.
      if category and not (category == categoryPrev):
        code += '    // %s\n\n' % category

      code += '    %s(REGAL_CALL *%s)(%s);\n' % (rType, name, params)

      categoryPrev = category

    if api.name in cond:
      code += '#endif // %s\n' % cond[api.name]
    code += '\n'


  # Close pending if block.
  if categoryPrev:
    code += '\n'

  code += '  };\n'

  return code

dispatchHeaderTemplate = Template( '''${AUTOGENERATED}
${LICENSE}

#ifndef __${HEADER_NAME}_H__
#define __${HEADER_NAME}_H__

#include "RegalUtil.h"

REGAL_GLOBAL_BEGIN

#include <GL/Regal.h>

REGAL_GLOBAL_END

REGAL_NAMESPACE_BEGIN

namespace Dispatch
{
${API_GLOBAL_DISPATCH_TABLE_DEFINE}

${API_DISPATCH_TABLE_DEFINE}

  // Lookup a function pointer from the table,
  // or deeper in the stack as necessary.

  template<typename T, typename F>
  F call(T &table, F *func)
  {
    RegalAssert(func);
    if (table._enabled && *func)
      return *func;

    T *i = &table;
    RegalAssert(i);

    RegalAssert(reinterpret_cast<void *>(func)>=reinterpret_cast<void *>(i));
    RegalAssert(reinterpret_cast<void *>(func)< reinterpret_cast<void *>(i+1));

    const std::size_t offset = reinterpret_cast<char *>(func) - reinterpret_cast<char *>(i);

    F f = *func;

    // Step down the stack for the first available function in an enabled table

    while (!f || !i->_enabled)
    {
      // Find the next enabled dispatch table
      for (i = i->next(); !i->_enabled; i = i->next()) { RegalAssert(i); }

      // Get the function pointer; extra cast through void* is to avoid -Wcast-align spew
      RegalAssert(i);
      RegalAssert(i->_enabled);
      f = *reinterpret_cast<F *>(reinterpret_cast<void *>(reinterpret_cast<char *>(i)+offset));
    }

    return f;
  }

}

struct DispatchTable
{
  bool           _enabled;
  DispatchTable *_prev;
  DispatchTable *_next;
};

struct DispatchTableGL : public DispatchTable, Dispatch::GL
{
  template<typename T> T call(T *func) { return Dispatch::call(*this,func);                                }
  inline DispatchTableGL *next()       { return reinterpret_cast<DispatchTableGL *>(DispatchTable::_next); }
};

struct DispatchTableGlobal : public DispatchTable, Dispatch::Global
{
  DispatchTableGlobal();
  ~DispatchTableGlobal();

  template<typename T> T call(T *func) { return Dispatch::call(*this,func);                                    }
  inline DispatchTableGlobal *next()   { return reinterpret_cast<DispatchTableGlobal *>(DispatchTable::_next); }
};

extern DispatchTableGlobal dispatchTableGlobal;
REGAL_NAMESPACE_END

#endif // __${HEADER_NAME}_H__
''')

def generateDispatchHeader(apis, args):

  substitute = {}

  substitute['LICENSE']         = args.license
  substitute['AUTOGENERATED']   = args.generated
  substitute['COPYRIGHT']       = args.copyright

  substitute['HEADER_NAME'] = 'REGAL_DISPATCH'
  substitute['API_GLOBAL_DISPATCH_TABLE_DEFINE'] = apiDispatchTableDefineCode(apis,args,['wgl','glx','cgl','egl'],'Global')
  substitute['API_DISPATCH_TABLE_DEFINE']        = apiDispatchTableDefineCode(apis,args,['gl'],'GL')

  outputCode( '%s/RegalDispatch.h' % args.srcdir, dispatchHeaderTemplate.substitute(substitute))
