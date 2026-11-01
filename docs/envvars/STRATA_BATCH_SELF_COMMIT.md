# `STRATA_BATCH_SELF_COMMIT`

調査対象: Strata main の HEAD c62d5e3a15b40ea51c96aae9e8d36928965f53ab（2026-11-01 時点）。

## 役割

複数 slot の batch window が「各 slot につき 1 行」のとき、window の GPU graph 自身に GDN 状態などを進めさせ、window 後の commit graph を省きます。変数は opt-in で、通常の単独 token window の self-commit とは別の batch 用条件です。実行時に batch window がなくても、設定値だけで通常の単独生成経路は変わりません。

## 値と判定

Verifier の env_on() は値全体を parse せず、未設定・空文字・先頭が 0 の値を off、それ以外の非空文字列を on とします。比較は大文字小文字を区別する文字 0 との比較だけです。

| 値 | 判定 |
|---|---|
| 未設定 | off |
| 空文字 | off（設定済みだが e[0] == '\0'） |
| 0、0anything | off |
| 1、true、false、2、anything | on |

この判定結果は src/core/verify.cpp のグローバル const bool g_batch_self_commit 初期化時に一度読み取られます。プロセス起動後に環境を変更しても Verifier の判定には反映されません。別の直接参照（下記「有効になる条件」）もあり、そこでは空文字を off、それ以外で先頭が 0 でなければ on とします。

根拠: src/core/verify.cpp:299-302,310-315。

## 有効になる条件

Verifier 側では、設定が on であり、batch window の行 ID がすべて異なる場合だけ batch_self_commits(rows, S) が true になります。行 ID の重複があれば false です。この条件は record_window() の batch_rec_ と組み合わせて keep_rows を決め、通常 batch launch の commit graph 省略にも使われます。したがって、各 slot に複数の proposal 行が入る window には適用されません。

STRATA_PIPED_MTP の可否判定では、src/program/generate.cpp がこの環境変数を別途直接読みます。値が未設定・空文字・先頭 0 ならこの理由による拒否はせず、空でない先頭 0 以外の値なら STRATA_PIPED_MTP を off にして stderr に次の警告を出します。

> STRATA_PIPED_MTP is off: it does not combine with STRATA_BATCH_SELF_COMMIT (the window would keep its rows itself)

ここでも文字列の全体 parse はありません。Verifier の global 判定とは別の読み取り時点です。

serve/server.py は、Linux 上で 2 slot 以上の CUDA Qwen engine を構成するとき、PARALLEL_STACK_ENV の一項目として "1" を env.setdefault() で設定します。既にサーバー環境または config の env に同名キーがあればその値を維持します。この自動設定は DeepSeek 4.1、SYCL/Metal/Vulkan、HIP、および Linux 以外には適用されません。strata_control/amd_four_card.py の AMD 4-card profile も "1" を提案値として使い、同名の親プロセス環境または config 値があればそれを優先します。これらは Strata 本体の既定値ではなく、各 Python launcher/profile が子 engine 用環境に値を設定する処理です。

根拠: src/core/verify.cpp:322-329,1281-1285,3777-3779,4581-4588; src/program/generate.cpp:6220-6238; serve/server.py:3670-3679,3702-3712; strata_control/amd_four_card.py:27,70-90。

## 実行時の詳細

batch window の記録時、keep_rows が true なら GDN convolution の multi-row kernel と GDN recurrence に keep 用の行情報を渡します。GDN groups の経路でも各 group に同じ keep 指示が渡ります（src/core/verify.cpp:1575-1585,1617-1647）。batch window はそのまま slot の row を保持するため、Verifier は対応する commit graph を capture せず、通常 batch launch の直後にも commit graph を launch しません。proposal を判定した後の commit_slot_prefixes() でも、self-commit 条件が true なら batch commit graph の launch と同期を省きます（src/core/verify.cpp:3777-3779,4516-4518,4542-4548,4578-4588）。

設定値が on のとき、batch verifier 初期化ログは「one-row windows keep their rows」という suffix を付けます。ただし、この起動ログは設定値を示すもので、個々の window の row ID がすべて異なることまでは示しません。各 batch graph の capture 時には strata verify: captured the batch window over slots ... が出ます。変数専用の失敗・終了経路は見つかりませんでした。関連する graph capture/launch が失敗した場合は既存の verify: ... エラーを返し、生成側が ERR <内容> を出す経路があります。

Strata の docs/BATCHING.md も opt-in switch として「one-row-per-slot window advances the GDN state itself, no commit graph」と記載しています（docs/BATCHING.md:110-123）。同文書には batch parity / 性能測定の説明もありますが、それらの測定結果はこの変数単独の一般的な性能保証としては扱っていません。

根拠: src/core/verify.cpp:3739-3741,3751-3774,1575-1585,1617-1647,4542-4548,4578-4588; src/program/generate.cpp:13419-13424; docs/BATCHING.md:110-123。

## 根拠

- 候補一覧には STRATA_BATCH_SELF_COMMIT が掲載されています（docs/envvars/000_envvers.md:619）。本体の読み取りは共通 helper を経由する src/core/verify.cpp:315 で確認しました。さらに src/program/generate.cpp:6223 が piped MTP との組み合わせ判定で直接読みます。
- verifier の batch path は src/core/verify.cpp:3744-3774 で batch window を capture し、src/core/verify.cpp:4578-4588 で launch します。single-token path にある別の self_commit は !batch_rec_ 条件付きであり、この変数の batch 条件とは区別されています（src/core/verify.cpp:1230-1233,3629-3632）。
- docs/BATCHING.md:492-495 は STRATA_BATCH_SELF_COMMIT 有効時に STRATA_PIPED_MTP を使えないことも説明しています。コード側では src/program/generate.cpp:6220-6238 が理由を出して piped MTP を無効化します。
