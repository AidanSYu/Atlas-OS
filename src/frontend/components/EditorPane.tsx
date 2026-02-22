'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Link from '@tiptap/extension-link';
import Highlight from '@tiptap/extension-highlight';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import {
  Bold,
  Italic,
  Strikethrough,
  List,
  ListOrdered,
  CheckSquare,
  Quote,
  Code,
  Heading1,
  Heading2,
  Heading3,
  Highlighter,
  Link as LinkIcon,
  Undo,
  Redo,
  Minus,
  Plus,
  Trash2,
  FileText as FileTextIcon,
  Save,
  Download,
} from 'lucide-react';

import { api, WorkspaceDraft } from '@/lib/api';
import { toastError, toastSuccess, toast } from '@/stores/toastStore';
interface EditorPaneProps {
  projectId: string;
}

function ToolbarButton({
  onClick,
  isActive,
  children,
  title,
}: {
  onClick: () => void;
  isActive?: boolean;
  children: React.ReactNode;
  title: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={`inline-flex h-7 w-7 items-center justify-center rounded-md transition-colors ${isActive
        ? 'bg-primary/20 text-primary'
        : 'text-muted-foreground hover:bg-surface hover:text-foreground'
        }`}
    >
      {children}
    </button>
  );
}

function Separator() {
  return <div className="mx-1 h-5 w-px bg-border" />;
}

const DEFAULT_DRAFT_ID = 'research_notes';

export default function EditorPane({ projectId }: EditorPaneProps) {
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasLoadedRef = useRef(false);

  const [drafts, setDrafts] = useState<WorkspaceDraft[]>([]);
  const [activeDraftId, setActiveDraftId] = useState<string>(DEFAULT_DRAFT_ID);
  const [isSaving, setIsSaving] = useState(false);

  const loadDraftsList = useCallback(async () => {
    try {
      const list = await api.listWorkspaceDrafts(projectId);
      setDrafts(list.sort((a, b) => b.updated_at - a.updated_at));
    } catch (e) {
      console.error("Failed to load drafts list", e);
    }
  }, [projectId]);

  useEffect(() => {
    loadDraftsList();
  }, [loadDraftsList]);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Placeholder.configure({
        placeholder: 'Start writing your research notes...',
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: { class: 'text-accent underline underline-offset-2' },
      }),
      Highlight.configure({
        multicolor: false,
      }),
      TaskList,
      TaskItem.configure({ nested: true }),
    ],
    content: '',
    editorProps: {
      attributes: {
        class: 'text-sm leading-relaxed text-foreground focus:outline-none min-h-[calc(100vh-200px)]',
      },
    },
    immediatelyRender: false,
    onUpdate: ({ editor: ed }) => {
      if (!hasLoadedRef.current) return;
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = setTimeout(async () => {
        setIsSaving(true);
        try {
          const content = ed.getJSON();
          await api.saveWorkspaceDraft(projectId, activeDraftId, content);
          await loadDraftsList();
        } catch (error) {
          console.error('Failed to save draft to workspace:', error);
        } finally {
          setIsSaving(false);
        }
      }, 1000);
    },
  });

  useEffect(() => {
    if (!editor) return;

    let isMounted = true;
    hasLoadedRef.current = false;

    // Clear content while loading new draft
    editor.commands.setContent('');

    async function loadDraft() {
      try {
        const draft = await api.getWorkspaceDraft(projectId, activeDraftId);
        if (isMounted && draft && draft.content) {
          editor?.commands.setContent(draft.content);
        }
      } catch (error: any) {
        // If it's a 404, it just means the draft doesn't exist yet, which is fine
        if (error.message && !error.message.includes('404')) {
          console.error('Failed to load draft from workspace:', error);
        }
      } finally {
        if (isMounted) {
          hasLoadedRef.current = true;
        }
      }
    }

    loadDraft();

    return () => { isMounted = false; };
  }, [editor, projectId, activeDraftId]);

  const addLink = useCallback(() => {
    if (!editor) return;
    const url = window.prompt('Enter URL:');
    if (url) {
      editor.chain().focus().setLink({ href: url }).run();
    }
  }, [editor]);

  if (!editor) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const handleCreateNewDraft = () => {
    const name = window.prompt("Enter a name for the new draft:");
    if (!name?.trim()) return;

    // Simple slugify
    const id = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');
    if (!id) return;

    setActiveDraftId(id);
  };

  const handleDeleteDraft = async (e: React.MouseEvent, draftId: string) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete ${draftId}?`)) return;

    try {
      await api.deleteWorkspaceDraft(projectId, draftId);
      if (activeDraftId === draftId) {
        setActiveDraftId(DEFAULT_DRAFT_ID);
      }
      await loadDraftsList();
    } catch (error) {
      toastError("Failed to delete draft");
    }
  };

  const handleExportMarkdown = async () => {
    if (!editor || !projectId) return;
    try {
      toast('Exporting markdown...', 'info');
      const contentStr = JSON.stringify(editor.getJSON());
      const result = await api.exportMarkdown({
        content: contentStr,
        citations: [],
        projectId: projectId,
        title: activeDraftId.replace(/_/g, ' ')
      });
      const blob = new Blob([result.markdown], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${result.filename || activeDraftId}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toastSuccess('Markdown export complete');
    } catch (error) {
      console.error('Failed to export markdown:', error);
      toastError('Failed to export markdown');
    }
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* Sidebar */}
      <div className="w-56 shrink-0 border-r border-border bg-card/50 flex flex-col">
        <div className="flex h-12 items-center justify-between border-b border-border px-3 shrink-0">
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
            <FileTextIcon className="h-3.5 w-3.5" />
            Workspace
          </h3>
          <button
            onClick={handleCreateNewDraft}
            className="rounded hover:bg-surface p-1 text-muted-foreground hover:text-foreground transition-colors"
            title="New Draft"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {drafts.map(draft => (
            <button
              key={draft.id}
              onClick={() => setActiveDraftId(draft.id)}
              className={`w-full group flex items-center justify-between rounded-md px-2.5 py-2 text-sm transition-colors ${activeDraftId === draft.id
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:bg-surface hover:text-foreground'
                }`}
            >
              <div className="flex items-center gap-2 truncate">
                <FileTextIcon className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate text-left">{draft.id.replace(/_/g, ' ')}</span>
              </div>
              {draft.id !== DEFAULT_DRAFT_ID && (
                <Trash2
                  className={`h-3.5 w-3.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity hover:text-destructive ${activeDraftId === draft.id ? 'text-primary/70' : 'text-muted-foreground'
                    }`}
                  onClick={(e) => handleDeleteDraft(e, draft.id)}
                />
              )}
            </button>
          ))}
          {drafts.length === 0 && (
            <div className="px-2 py-4 text-center text-xs text-muted-foreground">
              No drafts found
            </div>
          )}
        </div>
        {/* Status indicator */}
        <div className="h-8 border-t border-border flex items-center px-3 text-[10px] text-muted-foreground bg-surface/50 shrink-0">
          {isSaving ? (
            <div className="flex items-center gap-1.5 animate-pulse text-primary">
              <Save className="h-3 w-3" /> Saving to workspace...
            </div>
          ) : (
            <div className="flex items-center gap-1.5">
              <Save className="h-3 w-3" /> Saved to workspace
            </div>
          )}
        </div>
      </div>

      {/* Editor Main */}
      <div className="flex h-full flex-1 flex-col min-w-0">
        {/* Toolbar */}
        <div className="flex shrink-0 flex-wrap items-center gap-0.5 border-b border-border bg-card px-3 py-1.5">
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            isActive={editor.isActive('heading', { level: 1 })}
            title="Heading 1"
          >
            <Heading1 className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            isActive={editor.isActive('heading', { level: 2 })}
            title="Heading 2"
          >
            <Heading2 className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            isActive={editor.isActive('heading', { level: 3 })}
            title="Heading 3"
          >
            <Heading3 className="h-3.5 w-3.5" />
          </ToolbarButton>

          <Separator />

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBold().run()}
            isActive={editor.isActive('bold')}
            title="Bold"
          >
            <Bold className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleItalic().run()}
            isActive={editor.isActive('italic')}
            title="Italic"
          >
            <Italic className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleStrike().run()}
            isActive={editor.isActive('strike')}
            title="Strikethrough"
          >
            <Strikethrough className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHighlight().run()}
            isActive={editor.isActive('highlight')}
            title="Highlight"
          >
            <Highlighter className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleCode().run()}
            isActive={editor.isActive('code')}
            title="Inline Code"
          >
            <Code className="h-3.5 w-3.5" />
          </ToolbarButton>

          <Separator />

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            isActive={editor.isActive('bulletList')}
            title="Bullet List"
          >
            <List className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            isActive={editor.isActive('orderedList')}
            title="Numbered List"
          >
            <ListOrdered className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleTaskList().run()}
            isActive={editor.isActive('taskList')}
            title="Task List"
          >
            <CheckSquare className="h-3.5 w-3.5" />
          </ToolbarButton>

          <Separator />

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            isActive={editor.isActive('blockquote')}
            title="Blockquote"
          >
            <Quote className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().setHorizontalRule().run()}
            title="Divider"
          >
            <Minus className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton onClick={addLink} isActive={editor.isActive('link')} title="Add Link">
            <LinkIcon className="h-3.5 w-3.5" />
          </ToolbarButton>

          <div className="flex-1" />

          <ToolbarButton onClick={handleExportMarkdown} title="Export Markdown">
            <Download className="h-3.5 w-3.5" />
          </ToolbarButton>
          <Separator />
          <ToolbarButton onClick={() => editor.chain().focus().undo().run()} title="Undo">
            <Undo className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton onClick={() => editor.chain().focus().redo().run()} title="Redo">
            <Redo className="h-3.5 w-3.5" />
          </ToolbarButton>
        </div>

        {/* Editor Content */}
        <div className="min-h-0 flex-1 overflow-y-auto bg-background">
          <div className="mx-auto max-w-3xl px-8 py-6">
            <EditorContent editor={editor} />
          </div>
        </div>
      </div>
    </div>
  );
}
