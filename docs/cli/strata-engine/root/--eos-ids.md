# `--eos-ids`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--eos-ids` |
| 別名 | なし |
| 値 | 0 以上 2,147,483,647 以下の整数 ID を1つ以上。カンマまたは空白区切り |

## 役割

生成結果中のどの token ID を end-of-sequence (EOS) として扱うかを指定します。標準 engine parser では、このオプションを指定すると EOS 停止も有効になります。省略時の標準 EOS ID は `248044` と `248046` です（`src/program/generate.cpp:706-708,2735-2738`）。

## 使い方

標準 engine parser を通るモデルで、token ID `2` または `3` が生成された時点で生成を止める例です。プロンプトの `--tokens` は別途必要です。

```sh
strata --pack ./pack --tokens "1,42,99" --eos-ids 2,3
```

複数 ID はカンマ区切り、または値の中の空白区切りで渡せます。shell で空白を含む値を渡す場合は引用符で囲みます（`src/program/generate.cpp:1097-1114,2735-2738`）。

## 値と既定値

- 値は必須です。直後の argv 要素がなく値が欠けると、`--eos-ids needs a value` を stderr に出して終了コード `2` で終了します（`src/program/generate.cpp:2416-2421,2735-2738`）。
- 値の中のカンマは空白に置き換えられ、空白区切りで各 token を読み取ります。各要素は10進整数として全体を読み取れる必要があり、範囲は `[0, 2147483647]` です。負数、範囲外、数字以外を含む要素は拒否されます（`src/program/generate.cpp:1097-1114`）。
- 空文字列、カンマだけ、空白だけなど、分割後に ID が一つもない値は拒否されます（同 `:1113-1114`）。
- 同じオプションを複数回指定した場合、パーサ helper がリストを消去してから読み込むため、最後に正常に解析されたリストが残ります。各指定で EOS 停止フラグも有効になります（同 `:1097-1114,2735-2738`）。
- パーサは要素の整数範囲と空リストを検証しますが、モデルの tokenizer がその ID を特別な EOS token と定義しているかまでは検証しません（同 `:1097-1114`）。

## 実行時の動作

- `Options` の初期値は `eos_ids = {248044, 248046}`、`stop_eos = false` です。`--eos-ids` を解析すると指定 ID で既定リストを置き換え、`stop_eos = true` にします（`src/program/generate.cpp:706-708,2735-2738`）。
- `--stop-eos` は既定 ID リストを保ったまま停止フラグだけを有効にする別 option です。両方を指定した場合、`--eos-ids` がどちらの argv 順でもカスタムリストを設定し、停止を有効にします。複数の `--eos-ids` では最後のリストが使われます（同 `:2631,2735-2738,1097-1114`）。
- 通常の逐次生成では、プロンプト部分ではなく生成開始位置以降で `stop_eos` が有効かつ生成 ID がリストに含まれる場合に停止します（同 `:16076-16090`）。speculative decoding の逐次経路も生成 token を同じリストで判定し、EOS を出力した後にその round の続行を止めます（同 `:16680-16692`）。
- batch 経路では `eos_ids` との一致を使って slot を `stop` として完了させます。対象 ID は `BT` 出力されて生成数にも加算されたあとに完了判定されるため、EOS ID 自体も出力に含まれます（同 `:11603-11610,11640-11653,11822-11838`）。
- 逐次経路も、EOS と判定した token を生成列へ追加してから停止判定します。たとえば speculative 経路は `T <id>` を stdout に出してから EOS 判定し、EOS 時に round を終了します（同 `:14733-14746,15151-15169,16680-16692`）。

## 適用条件と副作用

- このオプションは `src/program/generate.cpp` の標準 parser で受理されます。モデルが Qwen3.6 (GGUF architecture `qwen35moe`) と判定される build では、parser より前の family switch が `strata::qwen35::run()` に全 argv を渡すため、標準 parser は使われません（`src/program/generate.cpp:2393-2407`）。
- Qwen3.6 専用 parser の通常の直接生成モードには `--eos-ids` の分岐がなく、未知引数として usage を stderr に出して終了コード `2` になります。Qwen3.6 実装の EOS 判定は固定 ID `248044` と `248046` で、カスタムリストを参照しません（`src/qwen35/q36_engine.cu:3072,3735-3795,3630-3638`）。
- Qwen3.6 の `--serve` モードでは、専用 parser は自身にない `--` option を無視し、次の argv 要素が option でなければ値として一緒に読み飛ばして stderr に警告します。このため `--eos-ids` は受理・適用されず、専用実装の固定 EOS ID が使われます（同 `:3782-3788,3072`）。
- この値によるファイル変更・ネットワーク通信は parser と EOS 判定箇所にはありません。影響は生成終了条件と生成出力に限られます。

## 出力とエラー

不正値の場合は `--eos-ids: <理由>` を stderr に出し、終了コード `2` で終了します。理由は `invalid token id: expected an integer in [0, 2147483647]` または `token list was empty` です。この parser 分岐は不正値に対して usage を追加表示しません（`src/program/generate.cpp:1097-1114,2735-2738`）。値がない場合の stderr と終了コードも `2` です（同 `:2418-2420`）。

## 根拠

- parser の初期値と EOS 説明コメント: `src/program/generate.cpp:706-708`
- 値の分割・整数範囲・空リスト検証: `src/program/generate.cpp:1097-1114`
- 標準 parser の必須値処理、`--stop-eos`、`--eos-ids` の登録: `src/program/generate.cpp:2416-2421,2631,2735-2738`
- 標準 parser の usage 表示には `--eos-ids` の項目がありません（usage の記載範囲: `src/program/generate.cpp:806-875`）。ソース parser では受理される一方、組み込み usage からは説明されない差があります。
- Qwen3.6 への family switch と専用 parser / EOS 処理: `src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3072,3735-3795`
