# `INK_SYCL_FORCE_SK_TRANSCODE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL backend が GGUF の expert を読み込む際、通常なら GGUF_RAW のまま native SYCL kernel で扱う型も、S_K 形式へ変換する経路に切り替える診断・比較用スイッチである。対象は `load_from_model_file()` 内で、モデルが GGUF かつ `gguf_adapter` がある場合に限る。`.strata` を読む `load()` ではこの変数を参照しない。SYCL backend が Strata 形式以外のモデルを `load_from_model_file()` に渡すことはあるが、GGUF 条件を満たさなければこのスイッチの分岐には入らない（`engine/src/inkling2/sycl/ink_sy_common.h:660-661,992-996,1121-1125`; `engine/src/inkling2/sycl/ink_sycl_backend.cpp:15-16,95-99`）。

対象 expert の directory entry の `gu_code_id` と `dn_code_id` が両方とも `FMT_GGUF_RAW` 以外なら、その expert は判定対象外である。raw entry について、変数が有効でなければ両方の GGML 型に SYCL kernel がある場合に native GGUF_RAW として記録する。有効なら、その kernel 対応の有無にかかわらず S_K code とレイアウトを選んで変換する。もともと両型に native kernel が揃わない entry は、変数が無効でも S_K 変換される（`engine/src/inkling2/sycl/ink_sy_common.h:358-378,1125-1147`）。

## 値と判定

`std::getenv` で設定有無を確認し、設定されている場合は `std::atoi` の結果が 0 以外かを判定する。文字列全体の妥当性検査はなく、`atoi` が先頭から読める符号付き十進整数部分を使う。空白と符号は整数変換規則に従い、最初の数字列より後ろは無視される。数字列が始まらない場合は 0 となる。したがって空文字は「設定済み」だが無効であり、`true` / `false` もこのコードでは有効値にならない（`engine/src/inkling2/sycl/ink_sy_common.h:1121`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| `load_from_model_file()` の GGUF + adapter 経路 | 無効（`force_sk_tc == false`） | `1`, `2`, `-1`, `+1`, ` 1`, `1abc`（`atoi` が非 0） | 空文字, `0`, `-0`, `0anything`, `abc1`, `true`, `false` |
| `.strata` の `load()`、または GGUF + adapter 条件外 | 当該変数を読まない | 該当なし | 該当なし |

値の範囲チェックや clamp はない。整数変換可能な値でも、`atoi` の `int` 範囲を超える入力の結果はこの実装で定義されないため、範囲外の挙動は保証できない（同上）。

## 有効になる条件

- `INK_SYCL_WITH_MODEL_FILE` を定義した SYCL backend が使われる。現行 backend translation unit はこの macro を定義して loader を含める（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:15-16`; `engine/src/inkling2/sycl/ink_sy_common.h:992-996`）。
- モデルファイル経由で `load_from_model_file()` が呼ばれ、`mf.kind == Gguf` かつ `mf.gguf_adapter` が存在する必要がある。通常の `.strata` 読み込みは別関数で、この変数を使わない（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:95-99`; `engine/src/inkling2/sycl/ink_sy_common.h:660-661,1125`）。
- 対象 expert に `FMT_GGUF_RAW` が含まれる必要がある。両 code がすでに raw 以外なら entry を変更しない。raw entry で両 GGML 型に SYCL kernel がない場合は、変数が未設定または無効でも S_K へ変換する（`engine/src/inkling2/sycl/ink_sy_common.h:1129-1147`）。
- コマンドライン引数や別環境変数による、この判定値の上書きは読み取り箇所にはない。変換後の expert 配置先（VRAM または Host-USM）は後続の VRAM budget 判定で決まり、この変数は配置を指定しない（`engine/src/inkling2/sycl/ink_sy_common.h:1190-1222,1232-1243`）。

## 実行時の詳細

`load_from_model_file()` の expert directory 計画時に値を評価する。関数呼び出しごとに読み直し、`static` cache はない。読み取った bool はその呼び出し中の `native_gguf` 配列と directory 計画に使われるため、読み取り後にプロセス環境を変更してもそのモデル読み込みには反映されず、次の load 呼び出しで再評価される（`engine/src/inkling2/sycl/ink_sy_common.h:995-999,1121-1147`）。

有効時、raw expert entry の code ID と body size を `choose_sk_code_for_ggml()` / `transcoded_sk_expert_layout()` の結果に置き換える。expert の読み込み時には native 配列が立っていないため `read_or_transcode_expert()` へ進み、raw body を読み取って GGUF_RAW から S_K へ変換する。無効時に native 配列が立った entry は `mf.read_expert_body()` で読み込み、directory の code と offset をそのまま使う。いずれも計画した expert を VRAM slab または Host-USM slab に格納する（`engine/src/inkling2/sycl/ink_sy_common.h:1134-1147,1153-1163,1218-1303`; `engine/src/inkling2/ink_gguf_transcode.h:404-448`）。

## ログと測定値

native 経路が 1 件以上あれば stderr に `[ink_sycl] native lossless GGUF_RAW SG16+XMX kernels active for %zu/%zu experts (zero S_K transcode)` を出す。変数を有効にしたことや変換件数を示す専用ログはない。load が成功すると通常の `[ink_sycl] loaded ...` 行が出るが、そこにはこの変数の値は含まれない（`engine/src/inkling2/sycl/ink_sy_common.h:1149-1151,1317-1324`）。

変換または後続ロードが失敗すると `load_from_model_file()` は `false` を返し、SYCL backend の `init()` も失敗する。呼び出し元 CLI は経路に応じて `init: <error>` または `[selfcheck] FAIL init: <error>` を stderr に出して終了コード 1 を返す。環境変数専用の警告・エラー文言はない（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:98-100`; `engine/src/inkling2/ink_main.cpp:117-120,143-145`）。

`docs/DETAILS.md` にはこの変数または SYCL のこの GGUF_RAW 分岐について対応する説明を確認できなかったため、測定値は記載しない。

## 根拠

- 値の読み取りと native / transcode の分岐: `engine/src/inkling2/sycl/ink_sy_common.h:1121-1151`
- native kernel 対応 GGML 型の判定: `engine/src/inkling2/sycl/ink_sy_common.h:358-378`
- SYCL backend の model-file loader 選択: `engine/src/inkling2/sycl/ink_sycl_backend.cpp:15-16,95-100`
- expert の native 読み込み / 変換処理: `engine/src/inkling2/sycl/ink_sy_common.h:1153-1163,1218-1303`; `engine/src/inkling2/ink_gguf_transcode.h:404-448`
- 成功ログと CLI の初期化失敗表示: `engine/src/inkling2/sycl/ink_sy_common.h:1317-1324`; `engine/src/inkling2/ink_main.cpp:117-120,143-145`
