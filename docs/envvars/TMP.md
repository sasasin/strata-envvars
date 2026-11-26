# `TMP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata が実際に `TMP` を判定して値を変える製品経路は、`terminal/serve/server.py` の `child_env()` が AMD/HIP backend 用に呼ぶ `hip_env_guard()` である。環境またはプロファイルの `env` にある一時ディレクトリ変数 `TMP` が空でなく、Strata がそのディレクトリへ一時ファイルを作れないと判定した場合、serve は書き込み可能な代替ディレクトリが見つかれば `TMP` をそこへ置き換えてエンジン子プロセスへ渡す。見つからなければ値は変更せず理由を stderr に出す。これは AMD/HIP 用の起動前補正で、他 backend ではこの検査・補正をしない（`terminal/serve/server.py:4007-4010, 4027-4028, 4054-4056, 4065-4095`）。

アプリ側では、Strata は `TMP` をエージェント子プロセスへ渡す標準環境変数の一つとして保持し、成果物追跡の除外パスにも追加する。これらは値を変更しない（`app/host/server/agent/harness-runtime.mjs:20-36, 75-83`; `app/host/server/agent/agent-bridge.mjs:181-190, 534`）。Windows インストーラーは既存インストール場所が `TMP` の下にあるかを調べ、その場合は保存場所の復元を行わない（`app/desktop/src-tauri/nsis/installer.nsi:1040-1067`）。

## 値と判定

serve は `TMP` を文字列として parse せず、他の二つの名前とともに `env.get(k)` で存在・空でないことを確認し、値をディレクトリパスとして `_dir_writable()` に渡す。後者はそのディレクトリ内に `TemporaryFile` を作れるかを試し、`OSError` なら書き込み不可とする（`terminal/serve/server.py:4078`; `terminal/serve/server_parts/engines.py:1083-1088`）。

| 条件 | unset | 有効になる値 | 無効になる値・扱い |
|---|---|---|---|
| serve の AMD/HIP backend | `TMP` が無ければ候補にならない | 空でない値のディレクトリに一時ファイルを作成できる場合、その値をそのまま維持 | 空文字は `env.get(k)` が偽なので検査されず、そのまま維持。空白、`0`、`1`、`true` なども真偽文字列として解釈せず、文字列どおりのパスとして検査する。作成できない場合は後述の代替先を探す |
| serve の CUDA / SYCL / その他 backend | 環境値を継承 | 値にかかわらず `TMP` 固有の Strata 検査はしない | `TMP` による補正・警告なし |
| デスクトップのエージェント起動 | 元の環境に無ければ追加されない | 名前が大文字小文字を問わず許可リストに一致すれば値を保持して渡す | `TMP` の値自体を判定・parse・補正しない。明示的な `extra` が同名値を持てば元環境の値を上書き |

serve の `child_env()` はまず `os.environ` のコピーを作り、次にプロファイルの `cfg["env"]` の各キーを文字列化して上書きするため、同じ名前ならプロファイル値が検査対象になる。CLI 引数から `TMP` を直接設定する処理は確認できない（`terminal/serve/server.py:4007-4010, 4027-4028`）。

## 有効になる条件

- 値の検査・補正が実行されるのは `cfg.get("backend") == "hip"` の場合だけ。OS 条件はこの分岐にない（`terminal/serve/server.py:4054-4056`）。
- `TMP` が未設定または空文字なら `bad` に含まれず、他の一時ディレクトリ変数も不正でなければ既定どおり変更されない（`terminal/serve/server.py:4078`）。
- `TEMP` / `TMPDIR` も同時に検査する。`TMP` が不正でも、他の変数が正常でも `TMP` は補正対象になる。不正な変数が複数あるときは、見つかった一つの代替ディレクトリをそれらすべてに設定する（`terminal/serve/server.py:4078-4089`）。
- 代替先は `cfg["log"]`、なければ `cfg["cwd"]`、なければ Strata の `ROOT` を基準にした親ディレクトリの `tmp`、続いて `ROOT/tmp`。ディレクトリを作成でき、`_dir_writable()` が成功した最初の場所を使う（`terminal/serve/server.py:4080-4089`）。どちらも使えない場合、`TMP` は不正な元の値のまま残る（`terminal/serve/server.py:4090-4094`）。
- 通常起動では `child_env()` の環境がエンジンの `Popen` に渡る。レプリカ・分割起動および split-engine fallback も `child_env()` を通るため、HIP backend の各子エンジン用に同じ補正が行われる（`terminal/serve/server.py:833-835, 8820-8824, 8850-8852, 8912-8919, 9391-9394`）。

## 実行時の詳細

`hip_env_guard()` は起動環境を作る `child_env()` の中で呼ばれ、子エンジンの生成より前に一度チェックする。プロセス起動後に環境を変えても、既に作成された子プロセスへは反映されない。関数内・モジュール内のキャッシュはなく、別の子エンジン環境を構築するたびに検査する（`terminal/serve/server.py:4007-4010, 4054-4056, 4078-4095`; `terminal/serve/server.py:833-835`）。

書き込み不可の判定は、ディレクトリの存在確認だけでなく、実際に一時ファイルを作る試行に基づく。代替ディレクトリ作成で `OSError` が起きた場合は次の候補へ進む。正常な値は維持し、代替先がない場合も起動を拒否せず、元値を残して警告を出す（`terminal/serve/server_parts/engines.py:1083-1088`; `terminal/serve/server.py:4080-4095`）。

## ログと測定値

`TMP` を含む不正値を代替先へ差し替えたとき、stderr に `strata serve: AMD: TMP=<元の値> is not writable: using <代替先>` を出す。代替先が見つからないとき、問題の変数名一覧に応じて `strata serve: AMD: TMP not writable (AMD's runtime needs a writable temporary folder)`（複数なら名前をカンマ区切り）を出す。正常値、未設定、空文字ではこの補正ログは出ない。これは Strata の診断文言であり、外部 AMD runtime の挙動を示す記述ではない（`terminal/serve/server.py:4086-4095`）。測定値は該当なし。

## 根拠

- `terminal/serve/server.py:4007-4010, 4027-4028, 4054-4056, 4065-4095` — serve 環境の構築、HIP 条件、判定、差し替え、ログ。
- `terminal/serve/server_parts/engines.py:1083-1088` — 一時ファイル作成による書き込み可能性判定。
- `terminal/serve/server.py:833-835, 8820-8824, 8850-8852, 8912-8919, 9391-9394` — 子エンジンへの環境受け渡し。
- `app/host/server/agent/harness-runtime.mjs:20-36, 75-83`; `app/host/server/agent/agent-bridge.mjs:181-190, 534` — エージェント環境の許可リスト転送と成果物追跡の除外指定。
- `app/desktop/src-tauri/nsis/installer.nsi:1040-1067` — インストール先復元時の `TMP` 下判定。
- `terminal/tools/vision/gguf_meta.h:136-155` は `TMP` を含む一時パス選択を行うが、呼び出し側は `gguf_meta_test.cpp` のみで、`terminal/tools/vision/CMakeLists.txt:124-142` ではテスト oracle 専用・`EXCLUDE_FROM_ALL` とされ、配布する `strata-vision` はリンクしない。そのため製品動作としては扱っていない。
