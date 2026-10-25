# `--cvec-mode`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--cvec-mode` |
| 別名 | なし |
| 値 | `add` または `project`（大文字小文字を区別） |

## 役割

`--control-vector` または `--control-vector-scaled` で読み込む制御ベクトルを、モデルの residual stream にどう適用するかを選びます。`add` はベクトルを加算し、`project` は residual stream からそのベクトル方向の成分を取り除きます。`src/program/generate.cpp:953-957`

## 使い方

```sh
engine/strata --pack /path/to/pack --tokens "1,2,3" \
  --control-vector-scaled /path/to/control-vector.gguf:1.0 \
  --cvec-mode project
```

この例では control-vector GGUF を読み込み、`project` モードで適用します。`--cvec-mode` 自体は制御ベクトルを読み込みません。

## 値と既定値

- 既定値は `add` です。内部値 `1` が `add`、`0` が `project` に対応します。`src/program/generate.cpp:797-803`
- `add` と `project` 以外は受け付けません。値は完全一致で判定されます。`src/program/generate.cpp:2722-2726`
- 値を省略すると共通 parser が stderr に `<option> needs a value` を出し、終了コード `2` で終了します。`src/program/generate.cpp:2416-2420`
- オプションを複数回指定した場合、parser は指定ごとに同じ設定値を更新するため、最後に解析した値が残ります。`src/program/generate.cpp:2722-2726`

## 実行時の動作

- `add` では、指定した control-vector ファイルの各 `direction.<layer>` を指定 scale で合成し、その値を各対象層で residual stream に加えます。カーネルは `h += v` を行い、合成と scale の適用はロード時に済ませます。`src/program/generate.cpp:1863-1866`、`src/program/generate.cpp:1872-1897`、`src/kernels/cuda/cvec.cu:87-94`
- `project` では、合成した層ベクトルを単位長に正規化し、そのノルムを scale として保持します。カーネルは `h -= s (h · v) v` を行うため、各対象層の residual stream からベクトル方向の射影成分を除きます。`src/program/generate.cpp:1912-1927`、`src/kernels/cuda/cvec.cu:67-85`
- モードは `--control-vector-layer-range` の対象範囲（両端を含む）内の層に適用されます。範囲の既定値は層 `1` から最終層までです。`--cvec-dir single:L` は `project` のときだけ層 `L` の方向を対象層全体で使い、`add` では per-layer 扱いになります。`src/program/generate.cpp:801-803`、`src/program/generate.cpp:1903-1925`
- 制御ベクトルが指定されている場合にだけロード処理が実行されます。したがって `--cvec-mode` 単独ではベクトル適用は起きません。`src/program/generate.cpp:3960-3968`
- `--serve` ではロード済みベクトルをリクエストごとに `cvec=0|1` で無効・有効にできます。値がない場合は有効です。切替時、エンジンはそのベクトル状態で作成した live session と checkpoint を無効化し、カーネルの有効フラグを更新します。`src/program/generate.cpp:12304-12308`、`src/program/generate.cpp:12335-12339`、`src/program/generate.cpp:12520`、`src/program/generate.cpp:12922-12927`
- ロードした mode、範囲、方向・scale のテーブルはセッション識別 digest に含まれます。標準エラーには mode、方向方式、層範囲、適用層数の要約が出ます。`src/program/generate.cpp:1930-1946`

## 適用条件と副作用

- control-vector GGUF の `general.architecture` が `controlvector` であること、少なくとも1つの `direction.<layer>` tensor があることが必要です。該当 tensor は対象モデルの embedding 幅と一致する f32 でなければロードに失敗します。layer 0 とモデルの層数以上の tensor は無視されます。`src/program/generate.cpp:1872-1897`
- `project` で指定した `single:L` にベクトルがない場合、対象範囲に有効な方向が一つもない場合、または GPU 側のテーブル確保・upload に失敗した場合はロードに失敗します。`src/program/generate.cpp:1905-1930`、`src/kernels/cuda/cvec.cu:26-38`
- `controlvector.model_hint` が存在して値が `qwen4exp` 以外の場合は stderr に警告しますが、この箇所ではロードを中止しません。`src/program/generate.cpp:1880-1883`
- `--serve` で制御ベクトルを切り替える際は、各デバイス上の有効フラグ更新前にデバイスを同期します。また切替前のベクトル状態で保存した session/checkpoint は再利用されません。`src/kernels/cuda/cvec.cu:137-149`、`src/program/generate.cpp:12922-12927`

## 出力とエラー

- 不正な mode 値では stderr に `--cvec-mode: add or project, got '<値>'` を出し、終了コード `2` を返します。`src/program/generate.cpp:2722-2726`
- 制御ベクトルのロード失敗では stderr に `strata generate: control vector: <理由>` を出し、終了コード `2` を返します。`src/program/generate.cpp:3963-3968`
- 成功時は stderr に `strata generate: control vector mode = ...` の要約を出します。`src/program/generate.cpp:1942-1946`

## 根拠

調査対象は指定 SHA の checkout にあるネイティブ engine parser `src/program/generate.cpp` と CUDA control-vector kernel `src/kernels/cuda/cvec.cu` です。checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありません。別 backend の実装差、Release 配布物、実行時の実測性能はこの調査では確認していません。
