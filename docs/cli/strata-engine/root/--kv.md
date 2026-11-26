# `strata generate --kv`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--kv` |
| 別名 | なし |
| 値 | `fp16`、`int8`、`q4_0`、`k8v4`。互換値 `q4` は `q4_0` として扱う |

## 役割

QSA attention の key/value (K/V) cache の保存形式を選ぶ。標準形式の `fp16` のほか、INT8、Hadamard rotation 後の Q4_0、K を INT8・V を rotated Q4_0 にする混合形式を指定できる。形式の選択は QSA state の K/V pool の要素型・配列構成と、attention の書き込み・読み出し経路に反映される（`engine/src/program/generate.cpp:5014-5027`、`engine/src/core/layer.cpp:813-824,863-878,1284-1299`）。

## 使い方

```sh
# Q4_0 K/V cache を指定して token 列を生成する
strata generate --pack /path/to/pack --tokens "1,2,3" --kv q4_0
```

## 値と既定値

- 省略時は `fp16`。`Options::kv` の初期値が `fp16` で、INT8・Q4・hybrid の各フラグは指定値に応じて切り替わる（`engine/src/program/generate.cpp:824,5014-5027`、`engine/src/core/layer.cpp:204-210,813-824`）。
- `fp16`: 通常の半精度 K/V pool を使う（`engine/src/core/layer.cpp:860,875-878`）。
- `int8`: K/V を INT8 code と scale で保持する。CLI の usage は 64 値ごとの fp16 scale と記載し、メモリ量を fp16 の半分と説明する（`engine/src/program/generate.cpp:1229-1230`）。
- `q4_0`: K/V を Hadamard rotation 後の Q4_0 pool に保持する（`engine/src/program/generate.cpp:1231-1232`、`engine/src/core/layer.cpp:867-869,1286-1299`）。
- `k8v4`: K を INT8、V を rotated Q4_0 で保持する hybrid 形式。CLI usage では 816 B/cell と記載されている（`engine/src/program/generate.cpp:1233-1234`、`engine/src/core/layer.cpp:757-762,863-866`）。
- `q4` は parser 後の検証前に `q4_0` へ変換される（`engine/src/program/generate.cpp:5014-5017`）。その他の値（空文字列を含む）は受理されず、stderr に許容値を出して終了コード `2` で終了する（同 `5015-5017`）。
- オプションを複数回指定した場合、parser は各指定を同じ文字列フィールドへ順に代入し、重複拒否を行わないため、後の値が残る（`engine/src/program/generate.cpp:3842-3847,3906`）。値を省略して引数列の末尾に `--kv` がある場合は `--kv needs a value` を stderr に出して終了コード `2` となる（同 `3844-3846`）。

## 実行時の動作

検証後、選択値に対応する QSA の global format flags を設定し、QSA state 初期化時に各形式に合う pool を構成する。INT8 は K/V code と scale 配列、Q4_0 は K/V 各々の Q4 配列、`k8v4` は K code・K scale・V Q4 の配列を使い、`fp16` は K/V の半精度配列を使う（`engine/src/program/generate.cpp:5019-5027`、`engine/src/core/layer.cpp:813-824,863-878`）。attention では選択形式に合う gather/dequantize 経路を通り、Q4_0 では query 側の rotation と attention 出力の逆 rotation も行う（`engine/src/core/layer.cpp:1284-1315`）。

`STRATA_KV_ROT` が先頭文字 `1` のときは INT8 形式にも rotation を有効化し、その値が `int8` の場合に stderr へ opt-in の通知を出す。Q4_0 は環境変数によらず rotation を使用する（`engine/src/program/generate.cpp:5021-5026`、`engine/src/core/layer.cpp:822`）。

`k8v4` は main QSA state に適用されるが、MTP draft state は hybrid のままではなく INT8 に切り替えて初期化される（`engine/src/core/mtp.cpp:518-524`）。`--kv-resident` による streaming との併用は CLI usage でサポート対象として明記されている（`engine/src/program/generate.cpp:1233-1237`）。このオプション単体はモデルファイルや設定ファイルを書き換えない。選択形式は GPU 上の K/V pool と attention の計算経路を変える。

この文書の対象は通常の `strata-engine root` parser である。エンジンはモデル family を判定し、Qwen3.6 では通常 parser に入る前に `engine/src/qwen35` 側へ処理を渡す（`engine/src/program/generate.cpp:3804-3818`）。Qwen3.6 の `--kv` は受理値・既定値が別なので、[Qwen3.6 用の文書](../qwen36/--kv.md)を参照。

## 適用条件と副作用

- K/V 形式は QSA state に設定される。Qwen3.6 family など別 parser に振り分けられる経路には、この文書の値規則を適用できない（`engine/src/program/generate.cpp:3804-3818`）。
- `--kv` は `--kv VALUE` の形で parser に登録されている。`--kv=VALUE` 形式を認識する分岐はありません（`engine/src/program/generate.cpp:3906`）。
- `--kv-resident` により host 側 K/V copy が必要となる場合、pinned RAM の確保に失敗すると streaming 初期化が失敗し、stderr に必要量と対処案を表示する（`engine/src/core/layer.cpp:920-937`）。この失敗は形式だけでは決まらず、実行時の割当状態にも依存する。
- backend ごとの可否を網羅する資料・分岐はこの調査範囲で確認できなかった。個々の GPU / driver での容量や性能、精度差も測定していないため、形式名や usage の説明を実測保証として扱わない。

## 出力とエラー

- 無効な値（`q4` を除く未知の値を含む）: `strata generate: --kv must be fp16, int8, q4_0 or k8v4` を stderr に出力し、`2` を返す（`engine/src/program/generate.cpp:5014-5017`）。
- 値がない: `--kv needs a value` を stderr に出力し、`2` で終了する（同 `3844-3846`）。
- `STRATA_KV_ROT=1` と `--kv int8` の併用時は rotation 有効化の通知を stderr に出す（同 `5023-5026`）。
- streaming 用 pinned RAM の確保失敗時の診断は「実行時の動作」の pinned RAM 項を参照（`engine/src/core/layer.cpp:930-937`）。

## 根拠

- `engine/src/program/generate.cpp:824,1208-1237,3906,5014-5032` — `strata generate` の parser スコープ、help 表示、既定値、値の検証、状態設定。
- `engine/src/program/generate.cpp:3804-3818` — Qwen3.6 family を専用実装へ渡す分岐。
- `engine/src/core/layer.cpp:738-766,807-878,920-937,1284-1315` — cache pool の割当形式、streaming host copy、attention の形式別読み書き。
- `engine/src/core/mtp.cpp:514-539` — `k8v4` 時の MTP draft K/V を INT8 で初期化する処理。
