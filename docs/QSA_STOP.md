# `QSA_STOP`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`QSA_STOP` は Metal の QSA prompt parity test が、`qsa_attn_mm` kernel の途中で処理を止める位置を指定する診断用変数です。Strata の通常実行経路では読み取られていません。リポジトリ全体の参照検索で、環境から読む箇所は `metal/tests/qsa_prompt_parity.cpp` のみです。

## 値と判定

test は `getenv("QSA_STOP")` が未設定なら `0`、設定されていれば `atoi()` の結果を Metal function constant 8 に渡します。文字列全体の検証はありません。`atoi()` が先頭の空白と符号の後に読む整数が `1`、`2`、`3`、`4` のときだけ対応する診断経路が選ばれます。たとえば `2junk` は `2`、空文字や整数として読めない文字列は `0` として扱われます。未設定・空文字・`0` は通常経路です。

| `atoi()` の結果 | `qsa_attn_mm` の処理 |
|---|---|
| `0` または `1`〜`4` 以外 | 通常の処理。`0` は既定動作 |
| `1` | ID と scale の準備・barrier の後、QK 計算前に戻る。partial の `m` と `l` に `1` を書く |
| `2` | QK 計算と barrier の後、softmax 前に戻る。`m` と `l` に `2`, `1` を書く |
| `3` | softmax と barrier の後、PV 計算前に戻る。`m` と `l` に `3`, `1` を書く |
| `4` | PV 計算後、旧 direct-store 経路で結果を出力する。現在の threadgroup-memory 経由の store を迂回する |

## 有効になる条件

この変数を読むのは `metal/tests/qsa_prompt_parity.cpp` の `qsa_prompt_parity` 実行ファイルだけです。同テストは `qsa_prompt.metal` をコンパイルし、環境値を `mtl::Constants().i(8, ...)` で pipeline に設定します。通常の engine 側の pipeline 作成箇所では function constant 8 を設定していないため、shader 側の既定値 `0` が使われます。したがって `QSA_STOP` を設定しても通常の Strata 推論動作は変わりません。

## 実行時の詳細

値は test の `main()` が `qsa_attn_mm` pipeline を作る際に読み取られ、コンパイル時定数として kernel に渡されます。pipeline 作成後の環境変更を再読込する処理はありません。値 `1`〜`3` は kernel の異なる中間地点で return するため、parity test の比較出力が通常実行時と異なり、診断目的で中間段階を切り分ける用途です。値 `4` は早期 return ではなく、PV 結果の書き込み方法を切り替える bisection 用経路です。

## 根拠

- `metal/tests/qsa_prompt_parity.cpp:23-28,41-42`: test 実行、Metal shader のコンパイル、環境値の `atoi()` と function constant 8 への設定。
- `metal/kernels/qsa_prompt.metal:19-22`: function constant 8 と未指定時の `0`。
- `metal/kernels/qsa_prompt.metal:35-50,88-107,108-145`: 値 `1`〜`4` による中間 return と store 経路。
- `metal/tests/qsa_prompt_parity.cpp:63-69,83-118`: parity test が対象 pipeline を実行し、結果を比較する箇所。

