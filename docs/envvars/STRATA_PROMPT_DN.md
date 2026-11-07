# `STRATA_PROMPT_DN`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal engine の prompt-chain 経路で使う routed-expert down GEMM のタイル値を指定します。値は `TM,TN,TK,SG` の順で `PromptBufs::dn3` に読み込まれ、v3 kernel の選択名、expert plan の down 側 tile 数、および dispatch の threadgroup size に反映されます。通常の decode や Metal の旧 v2 down kernel を使う場合にはこの指定は kernel 選択に使われません。

この名前の全参照を調べたところ、実行時に環境を読むのは `metal/src/engine/prompt_chain.inc:70` の `std::getenv` と、v6 用の既定値を選ぶ `:88` です。コメント参照は `:66` にあります。コメントはこの override を test tooling と呼びますが、読み取りには test/build 限定の guard がなく、上記の prompt-chain 条件で動作します。helper 経由や別の読み取り箇所は見つかりませんでした。

## 値と判定

最初の `pc_setup()` では、読み取り前に down tile を `[16, 64, 32, 2]` に初期化し、設定があれば `std::sscanf(e, "%d,%d,%d,%d", ...)` で配列へ直接読み込みます。戻り値を確認せず、値域検査・clamp もしません（`metal/src/engine/prompt_chain.inc:65-70`）。

| 環境の状態 | 初期値・変換結果 |
|---|---|
| 未設定 | `[16, 64, 32, 2]`。ただし v6 が有効なら下記の v6 既定値に置き換わります。 |
| 空文字 | `sscanf` は何も代入せず初期値を残します。環境変数自体は設定済みと判定されるため、v6 の既定値置き換えは抑止します。 |
| 4 個の変換に成功 | 各 `%d` の整数変換結果を対応する要素に代入します。 |
| 1〜3 個だけ変換できた | 変換できた先頭要素だけが更新され、残りはその時点の値を保ちます。後続の文字や区切りが不正でもエラー扱い・巻き戻しはありません。 |
| 先頭から変換できない | 初期値が残ります。設定有無は別に判定されるため、空文字と同様に v6 の既定値置き換えを抑止します。 |

`%d` は各整数の先頭にある空白や符号を受け付けますが、書式内のカンマは文字どおり一致する必要があります。4 個目の変換後の余分な文字列は検査されません。例えば `16,32,32,4tail` は4個の整数変換が完了します。読み取りコードは変換数を検査しないため、不完全・無効な値について警告や既定値への一括 fallback はありません。

`dn3[0]` は最終的に `STRATA_PROMPT_GU` 由来の plan tile height `b.tm` と一致させられます。一致しないと stderr に `strata metal: STRATA_PROMPT_GU/DN tile heights differ: using %d for both` を出して `dn3[0]` を `b.tm` に上書きします（`metal/src/engine/prompt_chain.inc:69-72, 91`）。したがってタプルの第1値は gate/up 側の `TM` と独立には指定できません。

## 有効になる条件

- Metal engine がビルドされていること。Metal CMake の `STRATA_METAL_ENGINE` が OFF なら engine の追加を行いません。また `METAL_CPP_DIR/Metal/Metal.hpp` が存在しない場合は device runtime と engine の構成を終了します。条件を通ると `metal/src/engine/*.cpp` が kernel library に含まれます（`metal/CMakeLists.txt:51-55, 73-77, 110-130`）。
- prompt が `Window::prompt()` に到達すること。`prompt_run_rows()` は `STRATA_METAL_PROMPT=window` でない場合、非 streaming かつ prompt 行数が `STRATA_METAL_PROMPT_MIN` 以上（未設定時 32）のときにこの経路を選びます（`metal/src/engine/window.cpp:3593-3599`）。
- streaming の場合、別の `STRATA_METAL_PROMPT_GEMM` / `STRATA_METAL_PROMPT_GEMM_MIN` による経路が選ばれると `prompt_gemm_init()` と `prompt_chunk()` が使われ、`prompt_chain.inc` の `pc_setup()` は呼ばれません（`metal/src/engine/window.cpp:3599-3615`）。`STRATA_PROMPT_DN` の読取は `pc_setup()` にあるため、この経路には適用されません。
- v3 down kernel を使うモデル・実行条件で値が kernel 選択に効きます。`b.v3e` は `COOP_K4` の判定結果と gate expert weight の型（type `< 144`）から決まります。v3e でなければ v2 kernel を使い、down tile は `dn2_tile()` で重み型から選ぶため、環境変数のタイル値は down kernel に反映されません（`metal/src/engine/prompt_chain.inc:26-46, 61-72, 464-475`）。
- `STRATA_PROMPT_V6` が v6 を有効にすると、対象 weight type が全層で対応していることが条件です。未設定時の v6 group size は 4、設定時は `atoi` の結果が 2 以上で有効となり最大 4 に clamp されます。v6 時は `dn3[0]` を 16 に固定します。さらに `STRATA_PROMPT_DN` が未設定なら down tile の残り3値を `[32, 32, 4]` にしますが、設定済みなら（空・無効値も含めて）その置き換えをしません（`metal/src/engine/prompt_chain.inc:73-90`）。

## 実行時の詳細

`Window::prompt()` は `pc_setup()` を呼び、`pc_setup()` は `b.C >= C` ならすぐ戻ります。初回は既定値を置いてから環境変数を読み、以降は選ばれた tile を down kernel 名 `mm_down3_<type>_<TM>_<TN>_<TK>_<SG>` または v6 の `mm_down6_<type>_<MS>_<TN>_<TK>_<SG>` に埋め込みます。v3e でない場合は type に応じた固定の `mm_down2_...` を選びます。down dispatch の threadgroup は v3/v6 では `32 * dn3[3]` です（`metal/src/engine/prompt_chain.inc:49-70, 449-477`）。

設定値は `pc_setup()` が初めて tile を組み立てた時に読み取られ、結果は `PromptBufs` に保持されます。`Window::prompt()` の chunk size `C` は function-local `static` として一度決まり、通常の同一 Window では後続の setup が `b.C >= C` で早期 return します。このため setup 後にプロセス環境を変更しても既存の tile 値は再読込されません（`metal/src/engine/prompt_chain.inc:49-51, 564-570`）。

不正なタイル値を Strata 側で検証したり、自動修正したりする処理はありません（`dn3[0]` と `b.tm` の不一致処理を除く）。値から作った kernel 名を `P_()` が `cx_->pipeline()` に渡します。Strata の当該コードには `STRATA_PROMPT_DN` 固有の失敗ログや fallback はありません。実際の pipeline 作成失敗の表示・終了挙動は Metal runtime 側の処理に依存するため、ここでは断定しません（`metal/src/engine/window.cpp:272-278`; `metal/src/engine/prompt_chain.inc:464-475`）。

## 根拠

- `metal/src/engine/prompt_chain.inc:49-72, 83-91` — setup の早期 return、tile の初期化と parse、v3e/v6 の条件、v6 既定値、TM 不一致時の警告。
- `metal/src/engine/prompt_chain.inc:449-477` — model type と v3/v6/v2 による down kernel 選択および dispatch size。
- `metal/src/engine/window.cpp:3593-3615` — prompt-chain 経路と streaming 経路の選択。
- `metal/CMakeLists.txt:73-77, 110-130` — Metal engine build 条件と engine source の組み込み。

`docs/DETAILS.md` および Strata の `docs/` に `STRATA_PROMPT_DN` の記載は見つかりませんでした。索引の候補名は実際の `getenv` 読み取りで確認できました。
