# `strata-engine` `--control-vector-layer-range`

- 調査対象 revision: `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`
- 調査日: 2026-11-25
- CLI scope: `strata-engine` のトップレベル `strata generate` parser（`root/`）

## 概要

control vector を適用するモデル層の範囲を、始点と終点の2つの整数で指定します。両端を含む範囲です。control vector 自体は `--control-vector` または `--control-vector-scaled` で読み込みます。この範囲オプションだけではベクトルを読み込まず、適用も有効になりません。

```text
strata generate ... --control-vector-layer-range A B
```

既定値はモデルの層 `1` から最終層までです。usage は「inclusive; default 1 .. the last」と示し、Options では範囲値を `-1, -1` で初期化しています（`engine/src/program/generate.cpp:1202-1204, 1370-1374`、SYCL 版 `engine/sycl/src/program/generate.cpp:794-796, 931-935`）。

## 値の解釈と適用

- `A` と `B` はそれぞれ `std::atoi` で整数化されます。数値として厳密に検証する処理や、`A <= B` の検証は parser にありません。値が不正な場合、`atoi` の結果が 0 となり、範囲処理側では既定境界として扱われます。2つの値のいずれかが不足すると `next()` が stderr に `--control-vector-layer-range needs a value` を出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3845, 4180-4183`）。
- 同じオプションを複数回指定すると、parser は同じフィールドを順に更新するため、最後の指定値が残ります（同 `engine/src/program/generate.cpp:4180-4183`）。
- 実際の範囲は始点 `A <= 0` なら `1`、終点 `B <= 0` またはモデル層数 `L` 以上なら `L - 1` に補正されます。層 `0` は対象外です（同 `engine/src/program/generate.cpp:2786-2787`）。したがって通常の有効範囲は `1 .. L-1` で、端点を含みます。
- 始点がモデルの最終層より大きい場合や、始点が終点より大きい場合は、範囲ループで対象層がなくなります。その結果「the control vector has no direction in layers A..B」として読み込み失敗になります（同 `engine/src/program/generate.cpp:2793-2813`）。

## 効果・適用条件

control vector ファイルが指定されている場合に限り、エンジンは model geometry の層数と埋め込み幅を使ってベクトルを読み込み、指定範囲の層に適用するテーブルを作成します（同 `engine/src/program/generate.cpp:2743-2748, 2793-2813`）。指定範囲外の層にはこのオプション由来のベクトルを適用しません。オプション単独で指定した場合は `cvec_files` が空のままなのでロード処理は呼ばれません（同 `engine/src/program/generate.cpp:6143-6150`）。

ロード成功時、範囲・モード・ベクトル内容を含む digest が生成され、診断行が stderr に出力されます。ロードは session 初期化より前に行われるため、以後に作られる実行グラフが設定済みカーネルを使います（同 `engine/src/program/generate.cpp:2741-2742, 2813-2829, 6142-6150`）。control vector の演算方法は `--cvec-mode`、範囲内の各層でどの方向を使うかは `--cvec-dir` が別途制御します。たとえば `single:L` は project mode で層 `L` の方向を範囲内で共有します（同 `engine/src/program/generate.cpp:2788-2809`）。

CUDA/HIP 系と SYCL 系の双方に同じ parser、範囲補正、ロード条件があります（SYCL: `engine/sycl/src/program/generate.cpp:1535-1539, 1577-1604, 2144-2147, 3266-3275`）。

## 失敗経路と副作用

指定範囲にベクトル方向が1層もない場合、または GGUF の形式・テンソルが不正、読み込み中に例外が発生、GPU 側へのアップロードに失敗した場合、`load_control_vectors` は失敗を返します。呼び出し側は `strata generate: control vector: <理由>` を stderr に出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:2750-2784, 2812-2813, 6145-6150`）。ロード成功時には GPU カーネル用のテーブルをアップロードし、stderr に mode・dir・層範囲・適用層数を出します（同 `engine/src/program/generate.cpp:2813, 2825-2829`）。

## 根拠

- `engine/src/program/generate.cpp:1202-1205, 1370-1374` — 既定フィールドと usage
- `engine/src/program/generate.cpp:3844-3845, 4180-4183` — 2値の取得、`atoi`、不足時の終了
- `engine/src/program/generate.cpp:2743-2787` — GGUF のロードと実効範囲の決定
- `engine/src/program/generate.cpp:2793-2829` — 対象層の処理、アップロード、digest と診断出力
- `engine/src/program/generate.cpp:6142-6150` — ベクトル指定時のロードと失敗終了
- SYCL 対応実装: `engine/sycl/src/program/generate.cpp:794-797, 931-935, 1535-1578, 1584-1621, 2144-2147, 3266-3275`
