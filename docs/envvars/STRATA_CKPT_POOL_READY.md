# `STRATA_CKPT_POOL_READY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

会話チェックポイント用の `CheckpointPool` に、保存時に再利用できる状態ベクトルを何個まで先行確保するかを指定します。値が有効なら、最初の serve 要求の前、および pool からチェックポイントを取り出した後に、足りない分をバックグラウンドで割り当てます。チェックポイント保存時の新しい状態ベクトル確保とページフォルトを減らすための設定です。

この変数だけでは pool は有効になりません。serve 経路で `STRATA_CKPT_POOL` が有効か、`STRATA_SLOT_CKPT_MOVE` が有効である必要があります。後者だけでも pool 自体は有効になります。値を読む実装は `src/program/generate.cpp` に一つだけあります（`src/program/generate.cpp:320-327`）。

## 値と判定

値は `std::atol` で `long` に変換され、1 未満は 0（先行確保なし）、1〜16 はその数、16 より大きい正数は 16 として扱われます。文字列全体の妥当性検査はなく、`atol` が読む先頭の数値部分が使われます。

| 環境変数の値 | 判定結果 |
|---|---|
| 未設定 | 0（先行確保なし） |
| 空文字、数値に変換できない文字列、`0`、負数 | 0 |
| `1`〜`16` | 指定数 |
| `17` 以上 | 16 |
| `3tail` | 3（後続文字は `atol` が読み飛ばす） |

先頭の空白や符号を含む文字列も `atol` の数値変換規則に従います。範囲外の整数文字列に対する個別の検査はありません。結果は関数内の `static const` に保存されるため、プロセス内で最初に評価された後の環境変更は反映されません（`src/program/generate.cpp:320-326`）。

## 有効になる条件

- この設定の pool と先行確保は `o.serve` の処理内にあります。通常の `generate` CLI 実行には適用されません（pool の構築位置は `src/program/generate.cpp:9333-9338,10393-10396`）。
- pool の有効条件は `STRATA_CKPT_POOL` の先頭文字が `0` 以外であること、または `STRATA_SLOT_CKPT_MOVE` の先頭文字が `0` 以外であることです。どちらも未設定なら pool は無効です。値全体を比較しないため、空文字も「設定あり」として有効になります（`src/program/generate.cpp:309-314,346-351,10393-10396`）。
- layer split がある（`stages` が空でない）場合は ready checkpoint を先行確保しません。初期状態サイズの `gdn` が 0 の場合も確保処理を行いません（`src/program/generate.cpp:10538-10541`）。
- ready pool の容量は、実際には `STRATA_CKPT_POOL_READY` の値と pool の有効条件で決まります。値が 0 なら先行確保せず、通常の pool は落とされたチェックポイントを再利用します。`STRATA_CKPT_POOL` が有効な場合でも ready 値が unset なら先行確保はありません（`src/program/generate.cpp:316-329,10538-10545`）。
- CLI 引数からこの値を上書きする処理はありません。serve 側の `parallel_stack_env` は Linux の2スロット以上の CUDA Qwen 設定で `STRATA_CKPT_POOL_READY=4` を `setdefault` します。設定ファイルまたは既存環境が値を持っていればその値が残り、CUDA/HIP engine への環境構築など該当条件も満たす必要があります（`serve/server.py:3670-3712,3763`）。この自動設定がない実行ではエンジンに渡された環境値が使われます。

## 実行時の詳細

serve 処理で `CheckpointPool` を構築すると、ready 数を最初に数値化して pool 上限にも使います。保持上限は `max(2, ready数)` です。したがって ready 値が 0 でも、pool が別途有効なら落とされたチェックポイントを最大2個まで保持できます（`src/program/generate.cpp:320-329,1944-1949,10393-10396`）。

serve 初期化時に `pool_topup()` が呼ばれ、ready 数までの不足分を非同期で確保します。チェックポイントを pool から取り出した後と、会話を park して pool のチェックポイントを消費した後にも補充を試みます。一度に走る補充 task は1つで、実行中なら次の補充を開始しません（`src/program/generate.cpp:10531-10557,10700-10722,10828-10840`）。

確保する各 checkpoint は現在の session の状態サイズを使って `gdn`、`ple`、`tails`、`dead`、`block_pos` の各 vector を resize します。したがってメモリ量はモデル状態に依存します。`docs/DETAILS.md` は Qwen3.8-Flash-Next の状態を約118 MBとして `N × 118 MB` と説明していますが、ソースは固定サイズを指定していません（`src/program/generate.cpp:10545-10554`; `docs/DETAILS.md:1506-1516`）。

環境値の不正を知らせる専用ログ、警告、終了経路はありません。ready 数が 0 または pool が無効・layer split 中・状態サイズ 0 なら補充をせず、通常の保存経路に進みます。先行確保の非同期処理にはこの箇所で明示的な例外捕捉や fallback ログがなく、割り当て失敗時の表示・回復動作はこの実装だけからは確認できません（`src/program/generate.cpp:10538-10555`）。

`docs/DETAILS.md` は、`STRATA_CKPT_POOL_READY` を `STRATA_CKPT_POOL=1` と併用し、先行確保数を1〜16にする設定として記載しています。実装上は `STRATA_SLOT_CKPT_MOVE` も pool を有効にし、先行確保の呼び出しは serve 初期化時にも行われるため、実際に確保される条件は上記のとおりです。資料記載の park 時間（`STRATA_PARK_ASYNC=1`、`STRATA_CKPT_GATHER=1` との併用）は資料中の測定値であり、この調査で再測定したものではありません（`docs/DETAILS.md:1508-1516`）。

## 根拠

- 変換・既定値・上限: `src/program/generate.cpp:316-329`
- pool 有効条件と保持動作: `src/program/generate.cpp:309-314,346-351,1940-1983,10393-10396`
- serve 起動時・補充時の条件と割り当て: `src/program/generate.cpp:9333-9338,10531-10557,10700-10722,10828-10840`
- サーバーによる既定値設定: `serve/server.py:3670-3712,3763`
- 文書に記載された測定条件と数値: `docs/DETAILS.md:1506-1516`
