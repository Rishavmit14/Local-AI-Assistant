import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { bracketMatching, defaultHighlightStyle, indentOnInput, syntaxHighlighting } from "@codemirror/language";
import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { drawSelection, EditorView, highlightActiveLine, highlightActiveLineGutter, keymap, lineNumbers } from "@codemirror/view";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

export interface PythonCodeEditorHandle {
  selectedText: () => string;
}

interface PythonCodeEditorProps {
  value: string;
  onChange: (value: string) => void;
}

export const PythonCodeEditor = forwardRef<PythonCodeEditorHandle, PythonCodeEditorProps>(
  function PythonCodeEditor({ value, onChange }, ref) {
    const host = useRef<HTMLDivElement>(null);
    const view = useRef<EditorView | null>(null);
    const changingFromProps = useRef(false);
    const onChangeRef = useRef(onChange);
    const initialValue = useRef(value);
    onChangeRef.current = onChange;

    useImperativeHandle(ref, () => ({
      selectedText: () => {
        const current = view.current;
        if (!current) return "";
        const selection = current.state.selection.main;
        return current.state.doc.sliceString(selection.from, selection.to);
      },
    }), []);

    useEffect(() => {
      if (!host.current) return;
      const editor = new EditorView({
        parent: host.current,
        state: EditorState.create({
          doc: initialValue.current,
          extensions: [
            lineNumbers(),
            highlightActiveLineGutter(),
            history(),
            drawSelection(),
            indentOnInput(),
            bracketMatching(),
            highlightActiveLine(),
            syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
            keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
            python(),
            EditorView.lineWrapping,
            EditorView.contentAttributes.of({
              "aria-label": "Canonical Practice Lab code",
              "aria-multiline": "true",
              spellcheck: "false",
            }),
            EditorView.updateListener.of((update) => {
              if (update.docChanged && !changingFromProps.current) {
                onChangeRef.current(update.state.doc.toString());
              }
            }),
            EditorView.theme({
              "&": { height: "100%", backgroundColor: "#0b1019", color: "#d2dbea" },
              ".cm-scroller": { fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace' },
              ".cm-content": { padding: "18px 0", caretColor: "#c9d3f8" },
              ".cm-gutters": { backgroundColor: "#0b1019", color: "#53627a", border: "none" },
              ".cm-activeLine, .cm-activeLineGutter": { backgroundColor: "rgba(112, 133, 176, .09)" },
              ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": { backgroundColor: "#33466d" },
              "&.cm-focused": { outline: "2px solid #9aaeff", outlineOffset: "-2px" },
            }),
          ],
        }),
      });
      view.current = editor;
      return () => {
        view.current = null;
        editor.destroy();
      };
    }, []);

    useEffect(() => {
      const editor = view.current;
      if (!editor || editor.state.doc.toString() === value) return;
      changingFromProps.current = true;
      editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: value } });
      changingFromProps.current = false;
    }, [value]);

    return <div ref={host} className="learning-code-editor" />;
  },
);
