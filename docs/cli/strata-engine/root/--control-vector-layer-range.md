# `--control-vector-layer-range`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--control-vector-layer-range` |
| 別名 | なし |
| 値 | 層番号 `A B` の2値。整数変換は `atoi`。help は inclusive と説明 |

## 役割

Control Vector を適用する層の範囲を指定します。範囲は両端を含みます。Control Vector ファイルの指定方法は [`--control-vector`](--control-vector.md) と [`--control-vector-scaled`](--control-vector-scaled.md)、適用方式は `--cvec-mode` / `--cvec-dir` です（この文書ではそれらの詳細は扱いません）。`src/program/generate.cpp:953-957`。

## 使い方

```sh
engine/strata --pack pack/full --tokens "1,2,3" \
  --control-vector-scaled /path/to/vector.gguf:1.0 \
  --control-vector-layer-range 4 44
```

これは engine の `generate` 引数構文に従った例です。Control Vector の実データとモデル形状が適合する必要があります。parser はオプションの直後から2つの argv 値を読みます。`src/program/generate.cpp:2416-2420, 2718-2720`。

## 値と既定値

- 値は開始層 `A` と終了層 `B` の2つです。どちらかが欠けると `<option> needs a value` を stderr に出し、終了コード 2 で終了します。`src/program/generate.cpp:2418-2420`。
- `atoi` で整数化されます。数値形式・範囲・`A <= B` の検証は parser にありません。`atoi` が数値として読めない値は 0 になり、数値の後ろに非数値文字が続く値も数値部分だけが変換されます。空文字も 0 相当です。`src/program/generate.cpp:2718-2720`。
- 未指定時は内部値 `-1, -1` から、開始 `A <= 0` は層 1、終了 `B <= 0` または `B >= L` は `L - 1` に補正されます（`L` はモデルの層数）。従って通常の既定範囲は `1..L-1` です。明示した開始値が `L` 以上の場合に 1 へ補正されることはなく、そのまま使われます。`src/program/generate.cpp:801, 1903-1904`。
- 同じ option を複数回指定すると、parser は各回2値を読み、後の値が先の値を上書きします。`src/program/generate.cpp:2718-2720`。

## 実行時の動作

この範囲は Control Vector ファイルをロードするときにのみ利用されます。`--control-vector` / `--control-vector-scaled` によるファイル指定がなければ `load_control_vectors` 自体を呼ばないため、範囲指定だけではロードや層変更は起きません。`src/program/generate.cpp:3961-3968`。

ロード時には、`first` から `last` までの各層を順に調べ、Control Vector にその層の方向がある場合に適用テーブルへ加えます。`first > last` や範囲外の開始値などでループ対象がなく、適用層が0なら `the control vector has no direction in layers A..B` を返してロードを失敗させます。範囲内にベクトルが存在しない層はスキップされます。`src/program/generate.cpp:1903-1930`。

Control Vector はモデル初期化の際に一度ロード・GPU upload されます。`--serve` では読み込まれた Control Vector を各リクエストで切り替える仕組みがありますが、このオプション自体は層範囲を指定するもので、リクエストごとに範囲を変更する処理は確認できません。`src/program/generate.cpp:3960-3968, 12304`。

## 適用条件と副作用

通常の `generate.cpp` 経路では、指定範囲は Control Vector の方向テーブルとスケールを構築し、`cvec_upload` に渡す層の範囲を制限します。ロード成功時は stderr に mode、方向、実範囲、適用層数を表示します。範囲外のベクトル tensor はロード時点で無視され、範囲内に有効な方向がなければ失敗します。`src/program/generate.cpp:1884-1897, 1903-1930, 1942-1946`。

Qwen3.6 family のモデルで family switch が有効な build では、通常の `Options` parser より前に `src/qwen35/q36_engine.cu` へ引数全体を渡します。そちらにはこの option の個別処理がありません。`--serve` では未対応 option として stderr に `ignoring ... (not an option of this engine)` を出し、次の値（通常の `A`）を読み飛ばしますが、その次の `B` は未知 option ではないため usage を出して終了コード 2 になります。値が2個渡る通常の書式はこの経路で受理されません。非 serve でも usage を出して終了コード 2 になります。したがってこの family 経路で通常 engine の Control Vector 範囲指定が適用されるとは確認できません。`src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3735-3747, 3782-3794`。

SYCL 側の `sycl/src/program/generate.cpp` にも同じ2値 parser と既定範囲補正があります（`sycl/src/program/generate.cpp:734, 1484-1485, 1995-1997`）。本調査では GPU 実行やビルドによる backend 別の実動作確認はしていません。

## 出力とエラー

- 値が不足した場合: `<option> needs a value` を stderr に出し、終了コード 2。`src/program/generate.cpp:2418-2420`。
- Control Vector のロードに失敗した場合: `strata generate: control vector: <理由>` を stderr に出し、終了コード 2。範囲内に方向がない場合の理由は `the control vector has no direction in layers A..B` です。`src/program/generate.cpp:1929, 3963-3968`。
- 成功時: 実効範囲と適用層数を stderr に表示します。`src/program/generate.cpp:1942-1946`。

## 根拠

- `src/program/generate.cpp:797-803, 953-957` — option 状態、既定値、help の説明。
- `src/program/generate.cpp:2416-2420, 2718-2720` — argv の値取得と parser。
- `src/program/generate.cpp:1863-1947, 3960-3968` — Control Vector の読込、範囲補正、層選択、upload、失敗・出力経路。
- `src/qwen35/q36_engine.cu:3735-3794` — Qwen3.6 family に委譲された場合の parser と未知 option の扱い。
- `sycl/src/program/generate.cpp:734, 860, 1484-1485, 1995-1997` — SYCL 側の状態、help、範囲処理。

調査は指定 checkout のソースと文書索引に限定しました。同一 revision の既存 CLI help、Release 配布物、各 backend の実行結果は確認していません。範囲の端点を超えた場合の loader 補正と、`atoi` が扱う値の挙動はソース実装から記述しています。
