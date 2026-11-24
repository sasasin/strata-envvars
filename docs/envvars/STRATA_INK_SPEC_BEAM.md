# `STRATA_INK_SPEC_BEAM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA Inkling backend の DSpark greedy speculative beam tree の幅 `beam_w` を設定する。値は `InkCudaBackend::init` で `spec_cfg_.beam` に入り、`dspark_spec_step_greedy` から `InkDSpark::draft_beam_tree` に渡る。幅が変わるのは draft tree の構成であり、生成 token は後段で trunk の greedy argmax に合う tree path から選ばれる。環境変数だけでは DSpark の有効化や tree 経路の選択は行わない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,1057-1079`）。

## 値と判定

CUDA backend の初期化時に `std::getenv` で設定有無を調べ、値があれば `std::atoi` で整数化する。文字列全体の検証はなく、空文字や数値に変換できない文字列は `atoi` の結果 0 となり、設定後の clamp で 1 になる。先頭の空白・符号と数字列の後ろの文字は `atoi` の規則に従う（例: `" 4tail"` は 4、`"true"` は 0）。変換後に `[1, 8]` へ clamp する。したがって、未設定なら既定値 4、`1`〜`8` はその値、0 以下は 1、9 以上は 8 になる。`atoi` の整数範囲外入力に対する結果は保証されない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,1201-1206`）。

| 条件 | unset | 有効になる値（例） | 無効・境界値の扱い |
|---|---|---|---|
| CUDA backend、CLI `--draft-beam` の正の値なし | `spec_cfg_.beam` 初期値 4 | `1`〜`8` はその値 | 空文字、`true`、`0`、負数は `atoi` 後 0 以下となり 1。`9` や `99` は 8。`4tail` は 4。 |
| CUDA backend、CLI `--draft-beam N` が正数に変換される | 環境値を読んだ後、正の `N` が優先 | `1`〜`8` はその値 | `N > 8` は 8。CLI の 0・負数・非数値は上書き条件を満たさず、環境値（または既定値）を使う。 |
| CPU / HIP / Metal / SYCL backend | この変数は読まれない | 該当なし | beam 設定への反映なし。 |

CLI parser も `--draft-beam` の引数を `atoi` で変換し、backend は `opts.spec_beam > 0` の場合だけ環境値を上書きする。従って CLI の `--draft-beam 0` は beam 0 を指定せず、環境値または既定値を残す（`engine/src/inkling2/ink_main.cpp:898-900`; `engine/src/inkling2/ink_backend.h:36-40`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:121-124`）。

## 有効になる条件

- `make_default_backend` が CUDA backend を選ぶ必要がある。CUDA build で `--cpu` を指定しない通常経路では CUDA backend が選ばれる。`--cpu` は CPU backend を選び、この環境変数を読まない。CUDA がなく、EP-CUDA / HIP / Metal / SYCL backend が選択される場合も、この変数の読み取り箇所はない（`engine/src/inkling2/ink_backend.h:177-215`; `engine/src/inkling2/ink_main.cpp:950-953`）。
- 値は `InkCudaBackend::init` で読み取られる。モデルを開き backend を初期化する実行経路が必要で、`--info` や tokenizer export のように backend 初期化前に終了するモードでは読まれない（`engine/src/inkling2/ink_main.cpp:1039-1044,1078-1094`）。
- tree 幅を実際に使うには CUDA backend で DSpark が有効かつ ready である必要がある。初期化は `opts.enable_dspark && model_.man.has_dspark && !model_.ls_active` のときだけ DSpark を構築する。`--draft off` は `enable_dspark` を false にする（`engine/src/inkling2/cuda/ink_cuda_backend.cu:343-350`; `engine/src/inkling2/ink_main.cpp:895-899`）。
- greedy tree step は slot 0、DSpark ready、`model_.ls_active` ではないこと、anchor/context/headroom 条件を満たす必要がある。満たさない場合 backend 関数は 0 を返し、呼び出し側の通常 decode / 別の speculative 経路へ進む（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1057-1076`; `engine/src/inkling2/ink_serve.h:876-889`）。
- serve の tree fast path は DSpark 使用中の単一 active request、prefill 完了、残り token 数と context の余裕があり、`STRATA_INK_SPEC` が `block` でなく、request が greedy かつ penalties なしの場合に呼ばれる。複数 request、sampling、penalties、`STRATA_INK_SPEC=block` ではこの beam tree 経路にならない。`STRATA_INK_SPEC=adapt` または `--draft-adapt` で一時的に drafting を抑制中も fast path を通らない（`engine/src/inkling2/ink_serve.h:507-515,876-890`）。

## 実行時の詳細

設定は `InkCudaBackend::init` のたびに環境から読み、backend メンバー `spec_cfg_` に保存する。関数内 static cache やリクエスト単位の再読込はなく、同一 backend の初期化後に環境を変更しても反映されない。backend を再初期化すればその時点の値を読む（`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,1201-1206`）。

serve の greedy tree path では `spec_cfg_.beam` が `draft_beam_tree` の `beam_w` 引数となる。`max_nodes` は別途 `min(12, runner_->tree_cap)` で決まり、tree を trunk 側で検証後、trunk の argmax と一致する子を辿って emit し、その path の状態だけ commit する（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1073-1108`）。serve は `n_emit` token を応答し、tree step が 0 を返した場合は block draft / 通常 batch decode へ移る（`engine/src/inkling2/ink_serve.h:876-930`）。

通常の直接 CLI 生成は `dspark_spec_step_greedy` を呼ばず、この環境変数で生成時の beam tree 幅は変化しない。CUDA backend 自体を初期化するため値の読み取りは発生する。bench と `--spec-check` は backend の speculative tree API を呼ぶが、これはそれぞれ単一 stream または診断経路である（`engine/src/inkling2/ink_main.cpp:131-148,198-235,599-608,672-700,1086-1120`）。

## ログと測定値

この環境変数の値・clamp・採用 beam 幅を示す専用ログや無効値警告はない。backend init が失敗した場合、呼び出し元は通常 CLI で `init: <理由>`、serve で `ERR init: <理由>` を出して終了するが、beam 値自体のエラーではない（`engine/src/inkling2/ink_main.cpp:1086-1090`）。`STRATA_INK_SPEC_LOG` が設定されていれば CUDA backend は 200 回ごとに speculative step の統計を stderr に出すが、beam 値の表示ではない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1115-1119`）。対象変数に結び付いた測定値は `docs/DETAILS.md` に見つからなかった。

## 根拠

- `engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125` — 環境値・CLI値の適用順と clamp。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:343-350` — DSpark 初期化条件。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:1057-1079` — speculative tree step 条件と beam 幅の使用。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:1103-1119` — tree path commit と任意統計ログ。
- `engine/src/inkling2/ink_backend.h:177-215` — backend 選択と build macro 条件。
- `engine/src/inkling2/ink_main.cpp:895-900,1039-1094` — CLI option と backend 初期化経路。
- `engine/src/inkling2/ink_serve.h:507-515,876-930` — serve の DSpark/tree 条件と fallback。
