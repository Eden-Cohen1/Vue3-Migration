# tests/test_composable_generator.py
from vue3_migration.core.mixin_analyzer import extract_lifecycle_hooks, extract_mixin_members
from vue3_migration.models import MixinMembers
from vue3_migration.transform.composable_generator import (
    mixin_stem_to_composable_name,
    generate_composable_from_mixin,
    _extract_func_params,
)

AUTH_MIXIN = """
export default {
  data() {
    return {
      isAuthenticated: false,
      currentUser: null,
    }
  },
  computed: {
    isAdmin() {
      return this.currentUser?.role === 'admin'
    },
  },
  methods: {
    logout() {
      this.isAuthenticated = false
      this.currentUser = null
    },
    checkAuth() {
      // check stored token
    },
  },
  created() {
    this.checkAuth()
  },
}
"""

MEMBERS = MixinMembers(
    data=["isAuthenticated", "currentUser"],
    computed=["isAdmin"],
    methods=["logout", "checkAuth"],
)


# ── name conversion ───────────────────────────────────────────────────────────

def test_mixin_stem_strips_mixin_suffix():
    assert mixin_stem_to_composable_name("authMixin") == "useAuth"

def test_mixin_stem_strips_mixin_suffix_lowercase():
    assert mixin_stem_to_composable_name("selectionmixin") == "useSelection"

def test_mixin_stem_no_suffix():
    assert mixin_stem_to_composable_name("auth") == "useAuth"

def test_mixin_stem_already_camel():
    assert mixin_stem_to_composable_name("selectionMixin") == "useSelection"

def test_mixin_stem_pagination():
    assert mixin_stem_to_composable_name("paginationMixin") == "usePagination"


# ── generated file structure ──────────────────────────────────────────────────

def test_generates_export_function():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "export function useAuth()" in result

def test_generates_ref_for_data():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "const isAuthenticated = ref(" in result
    assert "const currentUser = ref(" in result

def test_generates_computed():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "const isAdmin = computed(" in result

def test_generates_method():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "function logout(" in result
    assert "function checkAuth(" in result

def test_generates_return_statement():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "return {" in result
    for name in ["isAuthenticated", "currentUser", "isAdmin", "logout", "checkAuth"]:
        assert name in result.split("return {")[1]

def test_generates_vue_imports_ref():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "import {" in result
    assert "ref" in result.split("import {")[1].split("}")[0]

def test_generates_vue_imports_computed():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "computed" in result.split("import {")[1].split("}")[0]

def test_lifecycle_hook_inlined_for_created():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, ["created"])
    # created() is inlined (not wrapped in onCreated)
    assert "onCreated" not in result
    assert "checkAuth()" in result

def test_lifecycle_hook_wrapped_for_mounted():
    mixin = """
export default {
  mounted() { this.init() },
  methods: { init() {} },
}
"""
    members = MixinMembers(methods=["init"])
    result = generate_composable_from_mixin(mixin, "myMixin", members, ["mounted"])
    assert "onMounted" in result
    assert "import {" in result
    assert "onMounted" in result.split("import {")[1].split("}")[0]

def test_no_imports_when_no_vue_apis_needed():
    mixin = "export default { methods: { greet() { console.log('hi') } } }"
    members = MixinMembers(methods=["greet"])
    result = generate_composable_from_mixin(mixin, "greetMixin", members, [])
    # No ref/computed needed, no lifecycle hooks
    assert "export function useGreet()" in result
    assert "function greet(" in result

def test_this_refs_rewritten_in_methods():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    # In logout(), this.isAuthenticated -> isAuthenticated.value
    logout_body_start = result.index("function logout(")
    logout_section = result[logout_body_start:logout_body_start + 200]
    assert "isAuthenticated.value" in logout_section


# --- Bug 5: method body indentation in generated composables ---

def test_method_body_not_double_indented():
    """Method body lines should have exactly 4-space (inner) indentation,
    not original mixin indentation stacked on top of inner."""
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    # Find lines inside the logout() function body specifically
    lines = result.splitlines()
    in_logout = False
    body_lines = []
    for line in lines:
        if "function logout(" in line:
            in_logout = True
            continue
        if in_logout:
            if line.strip() == "}":
                break
            if line.strip():
                body_lines.append(line)
    assert len(body_lines) >= 2, f"Expected at least 2 body lines, found: {body_lines}"
    for line in body_lines:
        stripped = line.lstrip()
        indent_len = len(line) - len(stripped)
        assert indent_len == 4, (
            f"Expected 4-space indent (inner), got {indent_len}: {repr(line)}"
        )


# ---------------------------------------------------------------------------
# External dependency warning injection in generated composable
# ---------------------------------------------------------------------------

MIXIN_WITH_EXTERNAL_DEPS = """\
export default {
  data() {
    return {
      comments: [],
      newComment: '',
    }
  },
  methods: {
    loadComments(id) {
      this.comments = []
    },
  },
  mounted() {
    if (this.entityId) {
      this.loadComments(this.entityId)
    }
  }
}
"""


class TestExternalDepWarningsInComposable:
    def test_generated_composable_contains_external_dep_warning(self):
        members_dict = extract_mixin_members(MIXIN_WITH_EXTERNAL_DEPS)
        members = MixinMembers(**members_dict)
        hooks = extract_lifecycle_hooks(MIXIN_WITH_EXTERNAL_DEPS)
        result = generate_composable_from_mixin(
            MIXIN_WITH_EXTERNAL_DEPS, "commentMixin", members, hooks,
        )
        assert "as composable param" in result
        assert "entityId" in result

    def test_generated_composable_confidence_is_low(self):
        """External deps leave remaining this. refs → LOW confidence."""
        members_dict = extract_mixin_members(MIXIN_WITH_EXTERNAL_DEPS)
        members = MixinMembers(**members_dict)
        hooks = extract_lifecycle_hooks(MIXIN_WITH_EXTERNAL_DEPS)
        result = generate_composable_from_mixin(
            MIXIN_WITH_EXTERNAL_DEPS, "commentMixin", members, hooks,
        )
        assert "manual step" in result  # header indicates manual steps needed

    def test_no_warning_for_mixin_without_external_deps(self):
        """Clean mixin should not have external-dep warnings."""
        result = generate_composable_from_mixin(
            AUTH_MIXIN, "authMixin",
            MixinMembers(**extract_mixin_members(AUTH_MIXIN)),
            extract_lifecycle_hooks(AUTH_MIXIN),
        )
        assert "external dep" not in result


# ---------------------------------------------------------------------------
# Bug fix regression: Issue #4 — underscore-prefixed methods
# ---------------------------------------------------------------------------

class TestUnderscorePrefixedMethods:
    def test_underscore_prefixed_method_included(self):
        """Methods starting with _ should be included in the composable."""
        mixin = '''
    export default {
        methods: {
            _handleEscapeKey(event) {
                if (event.key === 'Escape') {
                    this.closeModal()
                }
            },
            closeModal() {
                this.isOpen = false
            }
        }
    }
    '''
        members = MixinMembers(data=['isOpen'], computed=[], methods=['_handleEscapeKey', 'closeModal'], watch=[])
        result = generate_composable_from_mixin(mixin, 'modalMixin', members, [])
        assert 'function _handleEscapeKey' in result
        assert 'function closeModal' in result

    def test_underscore_method_in_lifecycle_hook(self):
        """Underscore methods referenced in lifecycle hooks should be generated."""
        mixin = '''
    export default {
        methods: {
            _handleEscapeKey(event) {
                if (event.key === 'Escape') {
                    this.closeModal()
                }
            },
            closeModal() {
                this.isOpen = false
            }
        },
        mounted() {
            document.addEventListener('keydown', this._handleEscapeKey)
        },
        beforeDestroy() {
            document.removeEventListener('keydown', this._handleEscapeKey)
        }
    }
    '''
        members = MixinMembers(
            data=['isOpen'],
            methods=['_handleEscapeKey', 'closeModal'],
        )
        hooks = ['mounted', 'beforeDestroy']
        result = generate_composable_from_mixin(mixin, 'modalMixin', members, hooks)
        assert 'function _handleEscapeKey' in result
        assert 'onMounted' in result
        assert 'onBeforeUnmount' in result


# ---------------------------------------------------------------------------
# Bug fix regression: Issue #2 — lifecycle hooks not nested in computed
# ---------------------------------------------------------------------------

class TestLifecycleHookScope:
    def test_on_mounted_not_inside_computed_block(self):
        """onMounted must be at top-level scope, not nested inside a computed block."""
        mixin = '''
    export default {
        computed: {
            fullName() {
                return this.firstName + ' ' + this.lastName
            }
        },
        mounted() {
            console.log('component mounted')
        }
    }
    '''
        members = MixinMembers(computed=['fullName'])
        result = generate_composable_from_mixin(mixin, 'nameMixin', members, ['mounted'])
        assert 'onMounted' in result
        # The onMounted call should not appear within a computed(() => { ... }) block
        # Verify that 'onMounted' does not appear between 'computed(' and matching ')'
        import re
        computed_blocks = re.findall(r'computed\(\(\)\s*=>\s*\{[^}]*\}', result)
        for block in computed_blocks:
            assert 'onMounted' not in block


# ---------------------------------------------------------------------------
# Bug fix regression: Issue #3 — mounted + beforeDestroy both converted
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Bug fix regression: Issues #5, #6, #7, #8 — method body faithfulness
# ---------------------------------------------------------------------------

class TestMethodBodyFaithfulness:
    """Test that method bodies are preserved faithfully."""

    def test_all_methods_present_in_output(self):
        """All declared methods should appear in the generated composable."""
        mixin = '''
        export default {
            methods: {
                methodA() {
                    console.log('a')
                },
                methodB(x, y) {
                    return x + y
                },
                _privateMethod() {
                    this.doStuff()
                },
                async asyncMethod() {
                    await this.fetch()
                },
                methodC() {
                    this.value = 1
                }
            }
        }
        '''
        members = MixinMembers(
            data=['value'],
            computed=[],
            methods=['methodA', 'methodB', '_privateMethod', 'asyncMethod', 'methodC'],
            watch=[]
        )
        result = generate_composable_from_mixin(mixin, 'testMixin', members, [])
        for name in members.methods:
            assert f'function {name}(' in result, f"Method {name} missing from output"

    def test_deep_clone_preserved_verbatim(self):
        """JSON.parse(JSON.stringify(data)) should pass through unchanged."""
        mixin = '''
        export default {
            methods: {
                cloneData() {
                    return JSON.parse(JSON.stringify(this.items))
                }
            }
        }
        '''
        members = MixinMembers(data=['items'], computed=[], methods=['cloneData'], watch=[])
        result = generate_composable_from_mixin(mixin, 'testMixin', members, [])
        assert 'JSON.parse(JSON.stringify(' in result
        assert 'items.value' in result

    def test_method_body_preserved_with_dollar_refs(self):
        """Method bodies with this.$refs/this.$emit should be preserved, not emptied."""
        mixin = '''
        export default {
            methods: {
                handleClick() {
                    this.$emit('click', this.value)
                    this.$refs.input.focus()
                }
            }
        }
        '''
        members = MixinMembers(data=['value'], computed=[], methods=['handleClick'], watch=[])
        result = generate_composable_from_mixin(mixin, 'testMixin', members, [])
        assert 'function handleClick()' in result
        # Body should NOT be empty
        assert '{}' not in result.split('function handleClick()')[1].split('\n')[0]

    def test_static_arrays_preserved(self):
        """Hardcoded arrays in methods should not be truncated."""
        mixin = '''
        export default {
            methods: {
                getColors() {
                    return ['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'cyan', 'magenta']
                }
            }
        }
        '''
        members = MixinMembers(data=[], computed=[], methods=['getColors'], watch=[])
        result = generate_composable_from_mixin(mixin, 'testMixin', members, [])
        assert "'magenta'" in result or '"magenta"' in result

    def test_function_expression_method_extracted(self):
        """Methods declared as `name: function()` should be extracted."""
        mixin = '''
        export default {
            methods: {
                doWork: function(data) {
                    console.log(data)
                    return data
                }
            }
        }
        '''
        members = MixinMembers(data=[], computed=[], methods=['doWork'], watch=[])
        result = generate_composable_from_mixin(mixin, 'testMixin', members, [])
        assert 'function doWork(' in result
        assert 'console.log' in result  # body should be extracted


# ---------------------------------------------------------------------------
# Bug fix regression: Issue #3 — mounted + beforeDestroy both converted
# ---------------------------------------------------------------------------

class TestMountedAndBeforeDestroy:
    def test_both_hooks_generated(self):
        """Both onMounted and onBeforeUnmount should appear in the composable."""
        mixin = '''
    export default {
        data() {
            return { handler: null }
        },
        methods: {
            onResize() {
                console.log('resized')
            }
        },
        mounted() {
            window.addEventListener('resize', this.onResize)
        },
        beforeDestroy() {
            window.removeEventListener('resize', this.onResize)
        }
    }
    '''
        members = MixinMembers(
            data=['handler'],
            methods=['onResize'],
        )
        hooks = ['mounted', 'beforeDestroy']
        result = generate_composable_from_mixin(mixin, 'resizeMixin', members, hooks)
        assert 'onMounted' in result
        assert 'onBeforeUnmount' in result
        # Both should be in the imports
        import_line = result.split('\n')[0] if 'import' in result.split('\n')[0] else result.split('\n')[1]
        assert 'onMounted' in result.split("from 'vue'")[0]
        assert 'onBeforeUnmount' in result.split("from 'vue'")[0]


# ---------------------------------------------------------------------------
# Phase 6: Computed formatting improvements (Issue #26)
# ---------------------------------------------------------------------------

class TestComputedFormatting:
    """Test computed property formatting improvements."""

    def test_simple_computed_arrow_shorthand(self):
        """Single return statement should use arrow shorthand."""
        mixin = '''
        export default {
            data() {
                return { count: 0 }
            },
            computed: {
                doubled() {
                    return this.count * 2
                }
            }
        }
        '''
        members = MixinMembers(data=['count'], computed=['doubled'], methods=[], watch=[])
        result = generate_composable_from_mixin(mixin, 'testMixin', members, [])
        # Should use arrow shorthand, not block body
        assert 'computed(() => count.value * 2)' in result
        # Should NOT have block body form
        assert 'computed(() => { return' not in result

    def test_complex_computed_block_body(self):
        """Multi-line computed should use block body."""
        mixin = '''
        export default {
            data() {
                return { items: [] }
            },
            computed: {
                summary() {
                    const total = this.items.length
                    return `${total} items`
                }
            }
        }
        '''
        members = MixinMembers(data=['items'], computed=['summary'], methods=[], watch=[])
        result = generate_composable_from_mixin(mixin, 'testMixin', members, [])
        # Multi-line should use block body
        assert 'computed(() => {' in result

    def test_computed_single_expression_no_semicolon(self):
        """Arrow shorthand should strip trailing semicolons."""
        mixin = '''
        export default {
            data() {
                return { price: 0, tax: 0 }
            },
            computed: {
                total() {
                    return this.price + this.tax;
                }
            }
        }
        '''
        members = MixinMembers(data=['price', 'tax'], computed=['total'], methods=[], watch=[])
        result = generate_composable_from_mixin(mixin, 'testMixin', members, [])
        assert 'computed(() => price.value + tax.value)' in result
        # No semicolon inside the computed expression
        assert 'computed(() => price.value + tax.value;)' not in result


# ---------------------------------------------------------------------------
# Phase 6: Indentation normalization (Issue #28)
# ---------------------------------------------------------------------------

class TestIndentationNormalization:
    """Test that method bodies have consistent indentation."""

    def test_tab_indentation_normalized(self):
        """Tab-indented method body should be normalized to space indent."""
        mixin = "export default {\n  methods: {\n    doWork() {\n\t\tconst x = 1\n\t\treturn x\n    }\n  }\n}"
        members = MixinMembers(data=[], computed=[], methods=['doWork'], watch=[])
        result = generate_composable_from_mixin(mixin, 'testMixin', members, [])
        assert 'function doWork()' in result
        # Body should not contain tabs
        body_start = result.index('function doWork()')
        body_section = result[body_start:result.index('}', body_start) + 1]
        assert '\t' not in body_section


# ---------------------------------------------------------------------------
# Bug fix: _extract_func_params should match definitions, not call sites
# ---------------------------------------------------------------------------

METHODS_BODY_CALL_BEFORE_DEF = """\
    exportToCSV(data) {
        const blob = new Blob([data])
        this.downloadFile(blob, this.exportFileName)
    },
    exportToPDF(data) {
        const pdfBlob = createPDF(data)
        this.downloadFile(pdfBlob, this.exportFileName)
    },
    downloadFile(blob, name) {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = name
        a.click()
    },
"""

def test_extract_func_params_prefers_definition_over_call_site():
    result = _extract_func_params(METHODS_BODY_CALL_BEFORE_DEF, "downloadFile")
    assert result.strip() == "blob, name"

def test_extract_func_params_no_this_in_params():
    result = _extract_func_params(METHODS_BODY_CALL_BEFORE_DEF, "downloadFile")
    assert "this." not in result

def test_extract_func_params_shorthand_still_works():
    body = "    myMethod(a, b) {\n      return a + b\n    },"
    assert _extract_func_params(body, "myMethod").strip() == "a, b"

def test_extract_func_params_function_expression():
    body = "    myMethod: function(x, y) {\n      return x * y\n    },"
    assert _extract_func_params(body, "myMethod").strip() == "x, y"

def test_extract_func_params_arrow_function():
    body = "    myMethod: (a) => {\n      return a\n    },"
    assert _extract_func_params(body, "myMethod").strip() == "a"

def test_extract_func_params_no_match():
    body = "    someOtherMethod(x) {\n      return x\n    },"
    assert _extract_func_params(body, "nonExistent") == ""


# ---------------------------------------------------------------------------
# Import propagation from mixin to composable
# ---------------------------------------------------------------------------

from pathlib import Path

MIXIN_WITH_EXTERNAL_IMPORT = """\
import { helperUtil } from '../utils/helpers'
import { unusedThing } from '../utils/unused'

export default {
  data() {
    return { items: [] }
  },
  methods: {
    process() {
      return helperUtil(this.items)
    },
  },
}
"""

MEMBERS_WITH_IMPORT = MixinMembers(
    data=["items"],
    methods=["process"],
)

def test_generate_composable_includes_used_imports():
    result = generate_composable_from_mixin(
        mixin_source=MIXIN_WITH_EXTERNAL_IMPORT,
        mixin_stem="helperMixin",
        mixin_members=MEMBERS_WITH_IMPORT,
        lifecycle_hooks=[],
        mixin_path=Path("/project/src/mixins/helperMixin.js"),
        composable_path=Path("/project/src/composables/useHelper.js"),
    )
    assert "import { helperUtil } from '../utils/helpers'" in result

def test_generate_composable_excludes_unused_imports():
    result = generate_composable_from_mixin(
        mixin_source=MIXIN_WITH_EXTERNAL_IMPORT,
        mixin_stem="helperMixin",
        mixin_members=MEMBERS_WITH_IMPORT,
        lifecycle_hooks=[],
        mixin_path=Path("/project/src/mixins/helperMixin.js"),
        composable_path=Path("/project/src/composables/useHelper.js"),
    )
    assert "unusedThing" not in result

def test_generate_composable_rewrites_import_path():
    result = generate_composable_from_mixin(
        mixin_source=MIXIN_WITH_EXTERNAL_IMPORT,
        mixin_stem="helperMixin",
        mixin_members=MEMBERS_WITH_IMPORT,
        lifecycle_hooks=[],
        mixin_path=Path("/project/src/mixins/helperMixin.js"),
        composable_path=Path("/project/src/composables/deep/useHelper.js"),
    )
    assert "../../utils/helpers" in result

def test_generate_composable_no_paths_still_works():
    """Backwards compatible: no paths passed means no import propagation."""
    result = generate_composable_from_mixin(
        mixin_source=MIXIN_WITH_EXTERNAL_IMPORT,
        mixin_stem="helperMixin",
        mixin_members=MEMBERS_WITH_IMPORT,
        lifecycle_hooks=[],
    )
    assert "export function useHelper()" in result


DASHBOARD_MIXIN = """\
import { helperUtil } from '../utils/helpers'

export default {
  data() {
    return {
      stats: [],
      error: null,
      lastRefresh: null,
    }
  },
  computed: {
    totalCount() {
      return this.stats.length
    },
  },
  methods: {
    async loadStats() {
      this.error = null
      try {
        const data = await this.$store.dispatch('fetchStats')
        this.stats = data
        this.lastRefresh = Date.now()
      } catch (e) {
        this.error = e.message
      }
    },
  },
}
"""

def test_dashboard_mixin_import_not_used_excluded():
    """helperUtil is imported but never called in the mixin body -> excluded."""
    members = MixinMembers(
        data=["stats", "error", "lastRefresh"],
        computed=["totalCount"],
        methods=["loadStats"],
    )
    result = generate_composable_from_mixin(
        mixin_source=DASHBOARD_MIXIN,
        mixin_stem="dashboardMixin",
        mixin_members=members,
        lifecycle_hooks=[],
        mixin_path=Path("/project/src/mixins/dashboardMixin.js"),
        composable_path=Path("/project/src/composables/useDashboard.js"),
    )
    # helperUtil is imported but never referenced in any method body
    assert "helperUtil" not in result


# ── ordering tests ────────────────────────────────────────────────────────────

FULL_ORDERING_MIXIN = """
export default {
  data() {
    return {
      count: 0,
      name: '',
    }
  },
  computed: {
    doubled() {
      return this.count * 2
    },
  },
  methods: {
    increment() {
      this.count++
    },
    reset() {
      this.count = 0
    },
  },
  watch: {
    count(newVal) {
      console.log(newVal)
    },
  },
}
"""


class TestComposableOrdering:
    """Verify that generated composable code follows canonical ordering:
    refs -> computed -> methods -> watch."""

    def _generate(self, mixin_source, members, lifecycle_hooks=None):
        return generate_composable_from_mixin(
            mixin_source=mixin_source,
            mixin_stem="orderingMixin",
            mixin_members=members,
            lifecycle_hooks=lifecycle_hooks or [],
        )

    def test_refs_before_computed(self):
        members = MixinMembers(
            data=["count"],
            computed=["doubled"],
            methods=[],
        )
        mixin = """
export default {
  data() { return { count: 0 } },
  computed: {
    doubled() { return this.count * 2 }
  },
}
"""
        result = self._generate(mixin, members)
        ref_pos = result.index("ref(")
        computed_pos = result.index("computed(")
        assert ref_pos < computed_pos, "ref() declarations must appear before computed()"

    def test_computed_before_methods(self):
        members = MixinMembers(
            data=[],
            computed=["doubled"],
            methods=["increment"],
        )
        mixin = """
export default {
  computed: {
    doubled() { return 42 }
  },
  methods: {
    increment() { }
  },
}
"""
        result = self._generate(mixin, members)
        computed_pos = result.index("computed(")
        method_pos = result.index("function increment(")
        assert computed_pos < method_pos, "computed() must appear before function declarations"

    def test_methods_before_watch(self):
        members = MixinMembers(
            data=["count"],
            computed=[],
            methods=["increment"],
            watch=["count"],
        )
        mixin = """
export default {
  data() { return { count: 0 } },
  methods: {
    increment() { this.count++ }
  },
  watch: {
    count(newVal) { console.log(newVal) }
  },
}
"""
        result = self._generate(mixin, members)
        method_pos = result.index("function increment(")
        watch_pos = result.index("watch(")
        assert method_pos < watch_pos, "function declarations must appear before watch() calls"

    def test_full_ordering_with_all_sections(self):
        members = MixinMembers(
            data=["count", "name"],
            computed=["doubled"],
            methods=["increment", "reset"],
            watch=["count"],
        )
        result = self._generate(FULL_ORDERING_MIXIN, members)

        # Find first occurrence of each section marker
        ref_pos = result.index("ref(")
        computed_pos = result.index("computed(")
        method_pos = result.index("function increment(")
        watch_pos = result.index("watch(")

        assert ref_pos < computed_pos, "refs must come before computed"
        assert computed_pos < method_pos, "computed must come before methods"
        assert method_pos < watch_pos, "methods must come before watch"
