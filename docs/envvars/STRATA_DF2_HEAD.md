# `STRATA_DF2_HEAD`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DFlash2 drafter が候補語彙 subset の head を使う代わりに、target model の `output.weight` 全語彙行を使うかを切り替えます。CUDA/HIP では native head の行をそのまま DFlash2 の head 計算に渡し、subset 用の head 行コピーと語彙ファイル読み込みを避けます。Metal では Q8_0 に再量子化した head を使わず、target の head を既存の GEMV 経路で計算します。

DFlash2 の bind 時だけ効きます。DFlash2 を選ばない実行では、この値による head の切り替えはありません。CUDA/HIP では DFlash2 自体が native head (`--native`) を必要とします。

head 方式を選ぶ CLI 引数は確認できません。`--mtp-draft-vocab` や MTP の `draft_vocab.bin` は通常の subset ID を供給しますが、CUDA/HIP で native 条件が成立すればそのファイルを読まず、Metal で完全一致すれば読み込み後に subset を破棄します。別の環境変数による上書きもありません。

## 値と判定

判定は数値 parse や真偽値 parse ではなく、backend ごとの文字列比較です。

| Backend | native head を選ぶ値 | 未設定・空文字・その他 |
| --- | --- | --- |
| CUDA / HIP | 値の先頭文字が小文字 `n`。例: `native`, `no`, `never` | 選ばない。subset head の経路 |
| Metal | 文字列全体が大文字小文字を含めて `native` と一致 | 選ばない。Q8_0 head の経路 |

CUDA/HIP は `std::getenv()` の結果を `e[0] == 'n'` で判定するため、`native-extra` や `no` も native 扱いで、`Native` は該当しません。Metal は `std::string(hm) == "native"` の完全一致です。空文字はどちらでも native になりません。値は `static` に cache されず、CUDA/HIP の helper は呼び出しごとに環境を読みます。Metal は DFlash2 の bind 時に読み、bind 済みなら再評価しません。

## 有効になる条件

- DFlash2 が選択され、DFlash2 の head bind が実行される必要があります。通常の MTP head や他の drafter の head はこの変数で切り替わりません。
- CUDA/HIP では `head_device < 0` または head と drafter が同じ device の場合に限り native head を使います。layer split などで head が別 device にある場合、`bind()` 内の条件により subset 行の gather/copy 経路に戻ります。
- Metal では `Window::df2_bind()` が環境値を読み、完全一致の `native` のとき subset を消去します。
- CUDA/HIP で native head を使う場合、語彙全体分の DFlash2 logits を確保します。確保に失敗すると bind は `dflash2: the draft logits do not fit` を返します。top-k の行数上限を超える場合は `dflash2: the head has too many rows for the top-k` で失敗します。

## 実行時の詳細

CUDA/HIP の `head_native()` は環境変数を毎回読み、先頭文字で判定します。`Dflash2Drafter::bind()` は native 条件が成立し、かつ head が同じ device にあるとき、語彙ファイルの読み込みを飛ばして `head_rows` 全体を head として bind します。native 条件が成立しない場合は語彙ファイルから ID を読み、同一 device ならその行を gather し、別 device なら head 側で gather して drafter 側へコピーします。後続の head kernel は `n_dvocab_` 行で logits を計算し、top-k と selector に渡します。bind 成功時は stderr に `strata dflash2: ...-token draft head ...` の行数と VRAM 見積もりが出ます。

Metal は bind の冒頭で語彙ファイルを読み込み、MTP 側や packaged default の語彙も解決した後に `STRATA_DF2_HEAD` を判定します。完全一致の `native` なら、そこで語彙 subset を消して全語彙数を使います（このため Metal では native 指定でも先行する語彙ファイル読み込みの試み自体は省かれません）。native head の場合は `output.weight` を Q8_0 に変換せず `gemv()` に渡し、draft logits を計算します。その他の値では語彙 subset を Q8_0 に変換して行列経路で処理します。Metal の bind 成功ログは `strata metal: DFlash2 drafter ready (..., ...-token draft head ...), ...` です。

## 根拠

- `include/strata/core/dflash2.hpp:49-56` — CUDA/HIP DFlash2 bind の説明と `head_native()` の先頭文字判定。
- `src/core/dflash2.cpp:310-344` — native 条件（同一 device 条件を含む）、語彙ファイル読み込みの抑止、target head の行数取得。
- `src/core/dflash2.cpp:352-395` — 別 device / 同一 device の subset gather とコピー、bind への head 行数の受け渡し。
- `src/core/dflash2.cpp:287-306,396-400` — logits 確保・top-k 上限の失敗と bind 成功ログ。
- `src/core/dflash2.cpp:520-530` — DFlash2 の head kernel が native head と `n_dvocab_` を使い、結果を top-k に渡す箇所。
- `metal/src/engine/dflash2.inc:282-328` — Metal の vocab 読み込み後の完全一致判定、subset の消去、head 変換の分岐。
- `metal/src/engine/dflash2.inc:329-378,410-412,621-664` — Q8_0 変換と native GEMV の違い、bind 成功ログ、head 計算の分岐。
- `src/program/generate.cpp:5330-5355,6900-6924,11155,19704` — DFlash2 単独起動時の語彙ファイル要件判定、head メモリ見積もり、CUDA/HIP bind 呼び出し。
- `000_envvers.md:1013` — 候補一覧への掲載（実装根拠ではなく候補名の照合のみ）。
