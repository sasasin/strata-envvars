# `STRATA_PIPELINE_AUTO`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--pipeline-windows` を指定しなかったときに、対応する GPU 分割構成で `--pipeline-windows 2` を既定で有効にする自動選択を止めるスイッチです。値がゼロと変換されると自動選択は OFF になります。明示した `--pipeline-windows N` の値を上書きするスイッチではありません。読み取りは CUDA/HIP 共通の `engine/src/program/generate.cpp` と Intel SYCL の `engine/sycl/src/program/generate.cpp` にあります（それぞれ `:6560-6583`、`:3594-3619`）。

この機能が ON の場合、サーバー実行で分割ステージの検証ウィンドウを重ね、後段が現在のウィンドウを処理する間に前段が次のウィンドウを処理します。デコード窓のパイプライン動作は `engine/src/program/generate.cpp:13263-13288` にあります。変数自体は生成内容やトークンを指定せず、このパイプラインの自動選択だけに関与します。

## 値と判定

どちらの実装も自動選択分岐内で `static const char*` に `std::getenv` の結果を保存し、`std::atoi(...) == 0` で無効化を判定します。未設定 (`nullptr`) は無効化条件に当たらず、明示的な空文字は `atoi` が 0 を返すため無効化します。文字列全体の妥当性検査はなく、`atoi` が先頭の整数として変換した結果だけで判定します。したがって、例えば `0`, `-0`, `00`, `0anything`, `true`, 空文字は自動選択を止め、`1`, `2`, `-1`, ` 1tail` は止めません。先頭から整数に変換できない文字列は 0 として扱われます。読み取り値は自動選択の最初の評価時に static 保存され、同一プロセス中に環境を変更しても再取得されません（CUDA/HIP: `engine/src/program/generate.cpp:6561-6568`; SYCL: `engine/sycl/src/program/generate.cpp:3594-3607`）。

| 条件 | 未設定 | 自動選択を止める値 | 自動選択を止めない値 |
|---|---|---|---|
| HIP の自動選択分岐 | 変数による抑止なし | `atoi` 結果が `0`（例: `0`, 空文字, `true`, `0x`） | `atoi` 結果が非 `0`（例: `1`, `-1`, `2`） |
| Intel SYCL の自動選択分岐 | 変数による抑止なし | 同上 | 同上 |
| NVIDIA CUDA の自動選択分岐 | 自動選択はビルド条件で常に OFF | 値の判定に到達しない | 値の判定に到達しない |
| `--pipeline-windows N` を CLI で指定 | この変数を参照しない | この変数を参照しない | この変数を参照しない |

## 有効になる条件

- CLI で `--pipeline-windows` を指定せず、内部値が未指定を示す負値のままであること。CLI 指定値は `0..2` に clamp され、自動選択分岐を迂回します（HIP/CUDA: `engine/src/program/generate.cpp:4119`, `:6560-6561`; SYCL: `engine/sycl/src/program/generate.cpp:2096`, `:3594`).
- HIP: `--serve`、複数 GPU の実際のレイヤー分割、各ステージが別 GPU、ステージ数が最小数以上、かつ gfx12 decode-default 対象であることが必要です。最小ステージ数は `STRATA_PIPELINE_AUTO_MIN_STAGES` が設定されていれば `max(2, atoi(value))`、未設定なら MTP drafter を first-stage に置ける既定条件が成立する場合 2、それ以外は 3 です。空文字・非数値は `atoi` 結果 0 から最小 2 になります。さらに MTP (`--mtp`) と `--spec >= 2` があり、`--batch`（ただし `STRATA_PW_WITH_BATCH=1` なら solo path を許可）、`--peer-device`、helper cache、`--adapt-async`、MTP を使わない単独 DFlash2 経路が妨げにならないことが必要です。条件を満たさないと自動値は 0 になります（`engine/src/program/generate.cpp:6562-6579`）。
- Intel SYCL: `--serve`、別 GPU への二段レイヤー分割、両 GPU がアーキテクチャ ID によって Battlemage と判定されること、MTP と `--spec >= 2` が必要です。`--batch`, `--peer-device`, helper cache がある場合は有効になりません（`engine/sycl/include/strata/pipeline_auto.hpp:24-30`, `engine/sycl/src/program/generate.cpp:3596-3618`）。
- NVIDIA CUDA ビルドでは、この自動選択コードは `#if defined(STRATA_USE_HIP)` の `#else` で `on = false` にされるため、この環境変数で既定有効化はできません。明示 CLI は別経路です（`engine/src/program/generate.cpp:6567-6572`; gfx12 判定 helper: `:2849-2857`）。
- CLI で正の `--pipeline-windows` を明示した場合、後段の機能検証は別途実行されます。未対応条件では `strata generate: --pipeline-windows %d is off: %s` を stderr に出し、値を 0 にします（HIP/CUDA: `engine/src/program/generate.cpp:6584-6601`; SYCL: `engine/sycl/src/program/generate.cpp:3620-3634`）。

## 実行時の詳細

環境値の評価は生成コマンドの引数処理後、GPU 分割の準備・自動分割結果確定後に行われます。CLI 未指定の場合だけ `pw_auto` / `o.pipeline_windows < 0` が真となり、その場で環境値を参照して自動値を決定します。値がゼロと変換されると、他の条件がすべて整っていても `pipeline_windows` は 0 です。非ゼロなら他の条件との AND 判定を続け、成功時は 2、失敗時は 0 になります（HIP: `engine/src/program/generate.cpp:6560-6579`; SYCL: `engine/sycl/src/program/generate.cpp:3594-3615`）。

HIP の既定最小ステージ数は `STRATA_PIPELINE_AUTO_MIN_STAGES` と、MTP の first-stage 配置可否・`mtp_first_default_on()` に依存します。後者は HIP build で gfx12 の場合に既定 true、非 HIP では false です（`engine/src/program/generate.cpp:2860-2867`, `:6540-6545`, `:6563-6567`）。Intel SYCL はちょうど二段だけを自動選択し、三段以上は対象外です（`engine/sycl/include/strata/pipeline_auto.hpp:24-30`）。

自動有効になった場合、stderr に既定 ON のメッセージを出します。HIP 文言は `strata generate: --pipeline-windows 2 is on by default for a layer split of %zu stages (--pipeline-windows 0 or STRATA_PIPELINE_AUTO=0 turns it off)`、SYCL 文言は `strata generate: --pipeline-windows 2 is on by default for a layer split across two Arc B-series cards (--pipeline-windows 0 or STRATA_PIPELINE_AUTO=0 turns it off)` です。自動選択の条件を満たさない場合は通常この既定 ON メッセージは出ません（`engine/src/program/generate.cpp:6580-6583`; `engine/sycl/src/program/generate.cpp:3614-3619`）。

パイプライン実行時は各ステージに偶数・奇数窓用の verifier と stream/queue を用意し、窓間の hand-off を行います。stream/queue 作成失敗時は `strata serve: --pipeline-windows: stream creation failed` を stderr に出して終了コード 1 を返します。実行開始時は `strata serve: --pipeline-windows %d: two verifiers per stage, ... overlap across windows...` のログが出ます（CUDA: `engine/src/program/generate.cpp:13263-13288`, `:13756-13760`; SYCL: `engine/sycl/src/program/generate.cpp:7709-7738`, `:8035-8039`）。

## ログと測定値

自動選択が抑止されたことだけを示す専用ログはありません。自動選択の一般的な条件不足は静かに 0 にしますが、HIP で自動条件を通った後に単独 DFlash2 構成を検出した場合は `strata generate: --pipeline-windows is off by default here: DFlash2 drafts from the finished window's taps on every stage (--draft mtp keeps the pipeline)` を stderr に出して OFF にします（`engine/src/program/generate.cpp:6573-6579`）。明示 CLI の正値が機能条件を満たさない場合は `--pipeline-windows ... is off: ...` の理由を stderr に出します。文書 `docs/MULTI_GPU.md:182-200` は AMD gfx12 と Intel Battlemage の自動既定、無効化方法、パイプラインの概要を説明しています。そこに記された性能値は Intel Arc Pro B65 の条件付き説明であり、この環境変数単体の効果を測った値ではありません。

## 根拠

- `engine/src/program/generate.cpp:4119`, `:6532-6538`, `:6560-6583`, `:6584-6601` — CLI 値、HIP/CUDA 自動判定、ログと条件検証。
- `engine/src/program/generate.cpp:2847-2867`, `:6540-6545` — HIP gfx12 条件と MTP first-stage 既定。
- `engine/src/program/generate.cpp:13263-13288`, `:13756-13760` — CUDA/HIP パイプライン構成、失敗・開始ログ。
- `engine/sycl/src/program/generate.cpp:2096`, `:3590-3634` — SYCL の読み取り、判定、ログと条件検証。
- `engine/sycl/include/strata/pipeline_auto.hpp:9-30` — SYCL 自動有効条件。
- `engine/sycl/src/program/generate.cpp:7709-7738`, `:8035-8039` — SYCL パイプライン構成、失敗・開始ログ。
- `docs/MULTI_GPU.md:180-200` — Strata の機能説明との照合。
