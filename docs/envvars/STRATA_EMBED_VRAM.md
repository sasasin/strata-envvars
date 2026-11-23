# `STRATA_EMBED_VRAM`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

native IQ pack の `token_embd.weight` を通常の mapped pinned host memory に置く代わりに、条件を満たせば現在の GPU の VRAM にコピーする opt-in です。表のバイト列と gather/dequantize の処理は変わらず、配置だけが変わります（`engine/src/core/native_head.cpp:542-546,547-561,629-635`）。

この処理は `expert_layout().native` が true の native pack に対する `NativeEmbed::load` でだけ実行されます。通常 pack では読み取り箇所に到達しません。native pack は `--native`、`--spec T (T >= 2)`、`--prefill CHUNK` が必要で、`--keep-canonical` を指定した場合は embedding の load より前に終了します。embedding GGUF の入力は `--embd-gguf` があればそのファイル、なければ `--native` の shard 群です。これらの CLI 引数は入力・経路を決めますが、VRAM 配置の値を上書きしません（`engine/src/program/generate.cpp:3921-3924,5355-5357,5417,5753-5767`）。

## 値と判定

`NativeEmbed::load` が `std::getenv` で取得し、ポインターが非 null かつ先頭バイトが文字 `'1'` かだけを見ます。数値変換や文字列全体の比較はありません（`engine/src/core/native_head.cpp:547`）。

| 条件 | unset | VRAM 配置を試す値 | 試さない値 |
|---|---|---|---|
| native pack の embedding load | mapped pinned host memory を先に試す | 先頭文字が `1`（例: `1`, `10`, `1anything`） | 空文字、`0`, `2`, `true`, `TRUE`, ` 1` など |

大文字小文字・後続文字・数値としての妥当性は検査せず、先頭文字だけで判定します。unset と設定済み空文字はいずれも VRAM 配置を要求しません。`1` で要求しても、空き容量または確保・転送の条件を満たさなければ mapped host memory に fallback します（`engine/src/core/native_head.cpp:547-569`）。

## 有効になる条件

- `--pack` の expert layout が native pack と判定され、native embedding の初期化まで進む必要があります。通常 pack ではこの変数を読みません（`engine/src/program/generate.cpp:5417,5753-5767`）。
- embedding tensor が `token_embd.weight` で、モデルの埋め込み・語彙次元と一致し、対応する GPU dequantizer があり、次元・payload の検査を通る必要があります。満たさない場合は `NativeEmbed::load` が失敗し、呼び出し元は終了コード 1 を返します（`engine/src/core/native_head.cpp:516-539`; `engine/src/program/generate.cpp:5762-5765`）。
- VRAM を選ぶには `cudaMemGetInfo` が成功し、測定時の空きが embedding 表のバイト数に **512 MiB を加えた量より大きく**、さらに表の `cudaMalloc` と host-to-device `cudaMemcpy` が成功する必要があります。境界値ちょうどでは選びません（`engine/src/core/native_head.cpp:548-553`）。
- この環境変数の判定に連動する別の環境変数や CLI 配置オプションはありません。`--embd-gguf` は読み込む GGUF を選びます（`engine/src/program/generate.cpp:3923,5762-5763`）。
- VRAM に配置されるのは load 時の現在 device です。native embedding が VRAM にあり、DFlash2 drafter の device が 0 以外なら、その drafter の setup は拒否され、通常は MTP に fallback します。`--draft-fallback none` で MTP がない場合は serve 起動が終了コード 1 になります（`engine/src/core/native_head.cpp:547-553`; `engine/src/program/generate.cpp:13505-13527`）。

## 実行時の詳細

環境変数は `NativeEmbed::load` の呼び出し時に直接読みます。関数内 static cache はなく、このロードの後でプロセス環境を変更しても既に読み込んだ表の配置には反映されません。呼び出し元は native pack の初期化中にロードし、成功後に `set_native_embed` で参照を登録します（`engine/src/core/native_head.cpp:516-517,547-569`; `engine/src/program/generate.cpp:5753-5767`）。

条件を満たして VRAM コピーに成功すると、mapped host allocation は行わず、`dev_` にデバイス allocation を保持します。成功しない場合は `STRATA_EMBED_VRAM=1 not taken` を出して mapped pinned host memory を試します。後続の通常経路でも pinned allocation が失敗した場合には、変数が未設定でも VRAM コピーへ fallback する経路があります。HIP では mapped allocation の device alias が得られない場合にも VRAM へ fallback します（`engine/src/core/native_head.cpp:551-569,570-618`）。

登録後の token embedding gather は `dev_` を使います。Verifier の prompt window と layer の `embed_row` は native 表を選び、同じ `dev_` から行を読みます（`engine/src/core/verify.cpp:1642-1655`; `engine/src/core/layer.cpp:1345-1351`; `engine/src/core/native_head.cpp:629-635`）。

## ログと測定値

VRAM 配置成功時の stderr は `strata: native embedding: STRATA_EMBED_VRAM=1: %llu MiB placed in VRAM (%llu MiB were free)`、要求が通らない場合は `strata: native embedding: STRATA_EMBED_VRAM=1 not taken (%llu MiB free, the table needs %llu MiB plus 512 MiB): kept in mapped host memory` です。`cudaMemGetInfo` が失敗した場合、fallback 行の free 欄は `0` と表示されます。さらに通常の native pack 起動ログが `in VRAM` または `in mapped host memory` と最終配置を示します（`engine/src/core/native_head.cpp:554-568`; `engine/src/program/generate.cpp:5768-5774`）。

Strata の `docs/DETAILS.md:1784-1804` は CUDA の prompt switch の節で、この変数を含む4変数をまとめて有効にしたときの prompt +2.2%〜+2.6% を記載しています。節の測定条件は CMP 170HX (sm_80)、Qwen3.8-Flash-Next IQ3_S native pack、`--spec 3`、約3,000語の prompt、各 run で新しい engine を起動して reference と switch を交互に実行したものです。この値は4変数の合算であり、`STRATA_EMBED_VRAM` 単独の測定値ではありません。資料は個別寄与を示していません。

## 根拠

- 読み取り、空き容量・確保・転送判定、配置 fallback: `engine/src/core/native_head.cpp:542-569`
- mapped host memory と後続 VRAM fallback: `engine/src/core/native_head.cpp:570-618`
- native pack 経路と embedding GGUF の選択: `engine/src/program/generate.cpp:5355-5357,5417,5753-5774`
- 配置後の利用: `engine/src/core/native_head.cpp:629-635`, `engine/src/core/verify.cpp:1642-1655`, `engine/src/core/layer.cpp:1345-1351`
- DFlash2 の device 制約と fallback: `engine/src/program/generate.cpp:13505-13527`
- 資料にある4変数合算の測定と条件: `docs/DETAILS.md:1784-1804`
