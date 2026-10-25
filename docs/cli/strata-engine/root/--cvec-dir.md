# `--cvec-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。対象 checkout は `main` で、確認時点で未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数 parser） |
| オプション | `--cvec-dir` |
| 別名 | なし |
| 値 | `per-layer` または `single:L` |

## 役割

制御ベクトルの方向を、適用対象の各 layer 自身から取るか（`per-layer`）、指定 layer `L` から共通に取るか（`single:L`）を選びます。`single:L` は `--cvec-mode project` のときだけ参照されます。制御ベクトル自体を読み込む `--control-vector` または `--control-vector-scaled` と併用し、mode の既定値 `add` ではこのオプションによる方向選択は反映されません。parser が設定する初期値は per-layer です（`src/program/generate.cpp:797-803`）。

## 使い方

```sh
strata generate --pack ./pack --tokens "1,2,3" \
  --control-vector-scaled ./vectors/style.gguf:1.0 \
  --control-vector-layer-range 4 44 --cvec-mode project --cvec-dir single:12
```

`L` はモデル内の layer 番号です。実際に使用するには、指定した制御ベクトル GGUF に `direction.L` が含まれている必要があります。

## 値と既定値

- 省略時および `per-layer` 指定時は、適用対象 layer ごとにその layer の方向を使います。
- `single:L` は `single:` の後ろを `atoi` で整数化します。数値として厳密な書式かどうかは parser で検証されず、たとえば数値で始まらない suffix は `0` として解釈され得ます（`src/program/generate.cpp:2728-2732`）。
- 未指定時は `cvec_single = -1` で、per-layer です。`single:L` を指定しても mode が `add` の場合、実行時に `single` は `-1` に置き換えられ、方向選択には使われません（`src/program/generate.cpp:801-803,1903-1905`）。
- parser が認める値は `per-layer` と `single:` 接頭辞の値です。それ以外では stderr に `--cvec-dir: per-layer or single:L, got '…'` を出し、終了コード 2 で引数処理を終了します（`src/program/generate.cpp:2728-2732`）。

## 実行時の動作

制御ベクトルファイルの読み込み処理は、少なくとも1つの `--control-vector` / `--control-vector-scaled` がある場合に呼ばれます。したがって `--cvec-dir` 単独ではファイルを開かず、実行時の方向選択も行いません（`src/program/generate.cpp:3961-3969`）。

読み込み時、project mode で `single:L` が有効なら、`L` がモデル範囲内で、読み込んだファイル群にその layer の direction が存在することを確認します。条件を満たさない場合は `--cvec-dir single:L: the vector has no direction for that layer` を含むエラーを出し、初期化を終了コード 2 で中断します（`src/program/generate.cpp:1903-1908,3963-3968`）。有効なら、適用対象の各 layer `l` について方向元 `src` を `L` とし、方向ベクトルを読みます。per-layer では `src=l` です。適用対象範囲は `--control-vector-layer-range` によって決まります（`src/program/generate.cpp:1903-1916`）。

この文書の値選択は方向元を決めるもので、vector の演算方式は `--cvec-mode` が決めます。アップロードした vector は通常の layer 実行時と batched prefill の該当箇所で適用されます（`src/core/layer.cpp:1615-1625`; `src/prefill/prefill.cpp:4817-4822,4842-4845,4863-4875`）。`--serve` ではロード済み vector の有効・無効を request ごとの `cvec=0|1` に応じて切り替えます（`src/program/generate.cpp:12922-12928`）。

## 適用条件と副作用

- `single:L` の選択が実際に効くのは project mode かつ制御ベクトルがロードされる場合だけです。add mode では per-layer 扱いになります。
- 指定 layer の direction がない場合は起動時に拒否されます。指定番号が範囲外の場合も同じエラー経路です。負数は整数化後に single 選択として有効にならず、per-layer 扱いとなります（`src/program/generate.cpp:1903-1908`）。
- 単独ではファイルやネットワークへの副作用はありません。制御ベクトルをロードした場合は GPU 向けの vector table がアップロードされ、その内容がセッション識別 digest に含まれます（`src/program/generate.cpp:1930-1940`）。
- エンジンの CUDA/HIP 等の全 backend・build 構成で同じ経路が利用できるかは、このソース調査だけでは確認していません。

## 出力とエラー

方向元の検査失敗は `load_control_vectors` のエラーとして `strata generate: control vector: …` を stderr に出し、終了コード 2 で終了します（`src/program/generate.cpp:1906-1908,3963-3968`）。正常なロードでは mode、`dir` の種別、layer 範囲、実際に steer された layer 数を stderr に記録します。`single:L` が使われた場合は summary にも `singleL` が含まれます（`src/program/generate.cpp:1942-1947`）。

## 根拠

- parser 初期値とオプション説明: `src/program/generate.cpp:797-803,953-957`
- parser の値判定と `atoi` 処理: `src/program/generate.cpp:2728-2732`
- vector 読み込み、layer 検査、方向選択とアップロード: `src/program/generate.cpp:1867-1930`
- 初期化時の読込条件と失敗出力: `src/program/generate.cpp:3961-3969`
- layer 実行・prefill での適用箇所: `src/core/layer.cpp:1615-1625`; `src/prefill/prefill.cpp:4817-4822,4842-4845,4863-4875`
- `--serve` の request 単位切り替え: `src/program/generate.cpp:12922-12928`

調査範囲は指定 commit のソースと索引です。同一 revision の既存バイナリによる `--help` 表示や Release 配布物は確認していません。
