"""Rights-scoped diagnostic corpus: owner quotations + deterministic solver data.

Not a teacher-output corpus, historical-chat export, maturity holdout, or a
claim of owner-behavior competence. Each supervised owner target is an exact
quotation from the authorized execution directive, with exact source span.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

OWNER_ROWS=[
 ("device","phone_target","The primary runtime target is my Samsung SM-S948B on Android 17. It must work independently of Windows for ordinary AI usage."),
 ("diagnostics","evidence","Never fabricate execution, verification or progress."),
 ("coding","preservation","Preserve all existing functionality and data."),
 ("tools","original_bridge","Never replace the existing bridge with a new MCP gateway or disrupt working infrastructure."),
 ("memory","compression","Canonical requirements must never disappear because of conversation compression."),
 ("cross_app","ownership","Control owns shared general intelligence and orchestration. Specialist applications retain their authoritative engines, models, data and independent operation."),
 ("creative","ui_language","No slogans, generic promotional text, decorative AI theater, fake progress, meaningless cards or nonfunctional buttons."),
 ("cycles","verification","A model must never certify its own changes solely through self-assessment."),
 ("research","model_choice","SmolLM3-3B is diagnostic, not the final approved intelligence."),
 ("documents","completion","Do not treat passing compilation, successful inference, a pleasant UI screenshot or a downloaded model as completion."),
 ("reasoning","intelligence","Do not claim that the model is tailored merely because a configuration file or instruction prompt exists."),
 ("voice","reasoning_display","Never expose internal reasoning delimiters, debug scaffolding, raw exception strings or implementation placeholders as normal assistant responses."),
]
# Held out by distinct owner requirement; not unseen equivalent phrasing of
# a training quote. Even so, no semantic-independence/maturity claim is made.
HOLD_ROWS=[
 ("research","training_privacy","Train real adapters when feasible with available authorized computing. Research no-cost and alternative training methods, but do not incur paid costs or transfer private training data to external services without authorization."),
 ("cycles","intermediate_release","Do not install an intermediate APK merely to demonstrate incomplete code."),
 ("memory","history_scale","Implement working retrieval and reasoning across histories containing millions of tokens without pretending they fit inside one model context window."),
 ("coding","source_target","Use the current reconstruction branch as the integration target. Create isolated work branches if concurrent development requires them. Reconcile and merge verified changes without overwriting others' work."),
]

def build(destination:Path):
    destination.mkdir(parents=True,exist_ok=True)
    all_rows=OWNER_ROWS+HOLD_ROWS
    source='\n'.join(quote for _,_,quote in all_rows)+'\n'
    source_path=destination/'owner-quotations.txt';source_path.write_text(source,encoding='utf-8')
    source_sha=hashlib.sha256(source.encode()).hexdigest()
    def owner(domain,topic,quote):
        start=source.index(quote)
        return {'domain':domain,'source':f'owner-execution-directive-20261126:{topic}',
            'source_sha256':source_sha,'source_char_start':start,'source_char_end':start+len(quote),
            'rights_verified':True,'target_origin':'verbatim_owner_instruction',
            'messages':[{'role':'user','content':f'Recall the owner instruction recorded under {topic}.'},
                        {'role':'assistant','content':quote}]}
    train=[owner(*row) for row in OWNER_ROWS]
    holdout=[owner(*row) for row in HOLD_ROWS]
    # Exact arithmetic solver examples help reveal general-capability regressions.
    for group,pairs in ((train,[(7,8),(12,6),(19,4),(5,13),(11,9),(14,3),(8,16),(6,17)]),
                        (holdout,[(23,7),(18,9),(31,4),(17,13),(29,6),(37,8),(41,3),(26,11)])):
        for a,b in pairs:group.append({'domain':'reasoning','source':'deterministic-integer-multiplication-v1',
            'rights_verified':True,'target_origin':'deterministic_exact_solver',
            'messages':[{'role':'user','content':f'Calculate {a} multiplied by {b}. Return only the integer.'},
                        {'role':'assistant','content':str(a*b)}]})
    for name,rows in [('train.jsonl',train),('holdout.jsonl',holdout)]:
        (destination/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    manifest={'purpose':'owner_instruction_recall_diagnostic','owner_quotes_train':len(OWNER_ROWS),
        'owner_quotes_held_out':len(HOLD_ROWS),'arithmetic_train':8,'arithmetic_held_out':8,
        'source_sha256':source_sha,'rights_scope':'Owner-supplied instructions and deterministic exact solver targets only',
        'proprietary_teacher_outputs':False,'behavior_adaptation_certified':False,
        'semantic_independence_certified':False,'maturity_certified':False}
    (destination/'provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('destination',type=Path)
    print(json.dumps(build(p.parse_args().destination),indent=2))
