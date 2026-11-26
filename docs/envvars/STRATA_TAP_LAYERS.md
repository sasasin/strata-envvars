# `STRATA_TAP_LAYERS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_TAP_FILE` に verifier の各行について保存する層出力を選びます。単独では読み取られず、`STRATA_TAP_FILE` が未設定または空文字ならこの変数による tap は設定されません。通常の生成結果や層の計算を選ぶ設定ではなく、研究用ファイル出力の対象層を指定するフックです。読み取り箇所は `engine/src/core/verify.cpp` の `Verifier::init` です（同ファイル:1063-1107）。

CUDA/HIP 系の共通 verifier では、指定層の完成出力を tap buffer に格納し、window の行ごとに位置・入力 token・tap 値を `STRATA_TAP_FILE` へ書きます（同ファイル:2969-2982, 918-935, 4242-4243）。層出力の説明は `engine/include/strata/core/verify.hpp:707-710` にあります。

## 値と判定

`Verifier::init` が `STRATA_TAP_FILE` を読み、null または空文字なら file tap を無効にします。その file tap が有効なときだけ `STRATA_TAP_LAYERS` を読みます。変数が未設定または空文字なら文字列 `5,15,25,35,45` を使い、それ以外はカンマで分割した各部分文字列を `std::atoi` に渡します。全体の数値検証はなく、`atoi` が読める先頭の符号付き整数部分を使い、後ろの非数値文字は検査しません。したがって空要素や数字で始まらない要素は `0` になります（同ファイル:1063-1079, 1094-1107）。

各値 `l` は `0 <= l < g.n_layers - 1` の場合だけ採用されます。つまり有効な層番号は `0` から `n_layers - 2` までで、最後の層 `n_layers - 1` は対象外です（同ファイル:1079-1083, 1102-1107）。

| 条件 | unset / 空文字 | 設定値の例 | 無効・境界の例 |
|---|---|---|---|
| 単一 verifier（layer split なし）、かつ `STRATA_TAP_FILE` が非空 | `5,15,25,35,45` | `0,2`。空要素・`abc`・`2tail` は `atoi` によりそれぞれ `0`・`0`・`2` として扱う | 負数と `n_layers - 1` 以上は除外。値が一つも残らないと tap buffer 初期化エラー |
| layer split、かつ `STRATA_TAP_FILE` が非空で drafter が taps を設定していない | `5,15,25,35,45` | 同じ変換・範囲規則。残った層は昇順に並べ、重複を除く | 何も残らないと `STRATA_TAP_FILE` を無視する旨を stderr に出し、出力しない |
| `STRATA_TAP_FILE` が未設定または空文字 | 読み取られない | なし | `STRATA_TAP_LAYERS` の値にかかわらず file tap なし |

大文字小文字は数値変換に関係しません。先頭の空白と符号は `atoi` の変換対象ですが、要素全体の妥当性確認や空白除去処理はありません。layer split では採用後に sort と unique を行いますが、単一 verifier では重複を除去しません。後者では layer-to-slot 表が同じ層の slot を後の重複位置に設定します（同ファイル:1084-1085, 1109-1110）。

たとえば `0anything` は `0`、`true` と `false` はどちらも `0` と解釈されるため、層 0 が存在すれば採用されます。`1` は層 1 が存在すれば採用され、`-1` は除外されます。`n_layers - 2` は採用、`n_layers - 1` は除外です。

## 有効になる条件

- `STRATA_TAP_FILE` に非空のパスが必要です。空文字は null として扱われ、tap buffer も作られません（`engine/src/core/verify.cpp:1063-1068, 1094-1096`）。
- layer split で drafter がすでに `tap_req_` を設定している場合、環境変数の層指定は使われず、stage 0 は `strata: STRATA_TAP_FILE ignored: the drafter owns this layer split's taps` を出します（同ファイル:1073-1075, 1089-1093）。
- layer split で環境変数から少なくとも一層が選ばれた場合、stage 0 が file を所有し、各 stage が担当範囲の層を保持して chain の tap を集約します。選択層がなければ file は無視されます（同ファイル:1066-1071, 1080-1088, 1097-1107, 1131-1140）。
- `batch_rec_` 中の window は file に書かれません。層計算時の tap capture は `tap_batch_` で許可される場合がありますが、file への copy・write は通常の window に限定されています（同ファイル:2969, 3144, 4147, 4189, 4243）。
- `engine/src/core/verify.cpp` の Metal compile branch は環境変数を読む位置より前に `Verifier::init` から戻るため、この設定を読みません（同ファイル:978-993）。SYCL は別の `engine/sycl/src/core/verify.cpp` を使い、そこにこの名前の読み取りはありません。実装名の全検索では設定レジストリと DFlash2 README にも記載がありますが、それらは読み取り箇所ではありません。
- `Verifier::init` で他の読み取り箇所や CLI 引数による上書きは見つかりません。DFlash2 の `set_taps` は別の `tap_req_` 経路で、layer split では上記のとおり file tap を抑止します（`engine/src/core/verify.cpp:988-991, 1073-1093`）。

## 実行時の詳細

変数は verifier の初期化時に読み、各 `Verifier` が `tap_layers_` と `tap_slot_` に選択結果を保存します。static cache や request ごとの再読込はありません。初期化後にプロセス環境を変更しても、その verifier の選択済み層は変わりません。別 verifier を初期化すれば、その初期化時点で値を読みます（`engine/src/core/verify.cpp:956-975, 1073-1110`）。

file が非空なら `STRATA_TAP_FILE` を `wb` で開き、tap 数と埋め込み次元などのヘッダー、層番号を書きます。通常の verifier は `batch_rec_` でない window の各行について位置・入力 token と層出力を追記し flush します。layer split では stage 0 が chain の tap を集約して書きます（同ファイル:1121-1140, 918-935, 4185-4190, 4242-4243）。

全指定層が範囲外などで tap 数が 0 になった場合、単一 verifier は buffer 初期化に失敗し、`verify: the DFlash2 tap buffers could not be allocated` を返します。layer split では stage 0 が空リストの警告を出して file path を無効化するため、その理由だけでは初期化エラーになりません（同ファイル:1084-1093, 1111-1119）。file を開けなければ `verify: cannot write STRATA_TAP_FILE <path>` で初期化失敗します（同ファイル:1121-1124, 1131-1135）。

## ログと測定値

有効時の stderr は `strata: STRATA_TAP_FILE %s: %zu taps of %lld floats per row`、layer split では末尾に ` (layer split: gathered from every stage)` が付きます。layer split で有効層が一つもない場合は `strata: STRATA_TAP_FILE ignored: STRATA_TAP_LAYERS names no layer in 0..%d` です（`engine/src/core/verify.cpp:1087-1088, 1127-1127, 1140-1140`）。

処理時間・性能値はこのソースおよび関連する `terminal/tools/dflash2/README.md` に対象条件付きの測定値がないため記載しません。

## 根拠

- `engine/src/core/verify.cpp:956-993` — verifier 初期化と Metal 分岐。
- `engine/src/core/verify.cpp:1063-1119` — file 条件、layer split、既定値、パース、範囲判定、buffer 初期化。
- `engine/src/core/verify.cpp:1121-1140` — file 作成、ログ、layer split 集約ファイル。
- `engine/src/core/verify.cpp:2969-2982` — 層の完成出力を tap slot に格納。
- `engine/src/core/verify.cpp:918-935, 4185-4190, 4242-4243` — 行データの書き込みと実行経路。
- `engine/include/strata/core/verify.hpp:707-724` — tap の目的と保持状態。
- `engine/sycl/src/core/verify.cpp` — 独立した SYCL verifier 実装。`STRATA_TAP_LAYERS` の読み取りなし。
- `terminal/tools/dflash2/README.md:15-18` — 変数を `STRATA_TAP_FILE` と併用するという資料上の説明。詳細な値判定は上記ソースに基づきます。
