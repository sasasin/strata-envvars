# `DS4_LOOKAHEAD`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`STRATA_METAL` でビルドされた DSV41 のモデル処理において、現在の layer の router 入力から後続 layer の expert 選択を先に推定し、そのうち GPU に常駐していない CPU lane expert の重み行列を helper thread から prefetch します。先読み距離を指定し、実装上の最大距離は 2 layer です。これは予測に基づく読み込みであり、通常の layer の expert 選択そのものを置き換えるコードではありません。

## 値と判定

| 環境値 | 判定結果 |
|---|---|
| 未設定 | `d = 0`。無効。 |
| 空文字 | `std::atoi("")` により 0。無効。 |
| `0`、数字に変換できない文字列 | `atoi` の結果が 0 となり無効。 |
| 正の整数 | 変換値と 2 の小さい方を距離として使う。1 は 1 layer、2 以上は 2 layer。 |
| 負の整数 | `std::min(d, 2)` では負値のままなので無効。 |
| 数字の後ろに文字が続く値 | `atoi` は先頭の整数部分を変換する。例: `1tail` は 1、`3tail` は 3 から上限処理されて 2。 |

文字列全体の検証、下限 clamp、無効値の警告や fallback はありません。`atoi` の数値変換範囲外についても Strata 側の検査はありません。コードは `getenv` が返す文字列を `atoi` に渡し、結果を `std::min(d, 2)` で上限だけ制限します（`src/dsv41/ds4_model.cu:6550-6553`）。

## 有効になる条件

- 機能の定義と呼び出し箇所は `#if defined(STRATA_METAL)` の範囲内です。Metal 以外のビルドにはこの読み取り経路がありません（`src/dsv41/ds4_model.cu:6544-6553,10432-10448,10527-10529`）。
- 実行時に `T == 1`（単一 token の decode）である必要があります。先読み router の計算と prefetch 呼び出しの両方がこの条件で囲まれています。同じ layer の複数 token 処理では使われません（`src/dsv41/ds4_model.cu:10433-10435,10527-10529`）。
- 後続 layer がモデルの範囲内にあり、`nm == 1`、形式が `gg::kFmtMXFP4`、`gate_bias` と `gate_w` が非 null である間だけ、その layer の推定を行います。いずれかを満たさない layer で先読みループを止めます（`src/dsv41/ds4_model.cu:10435-10445`）。
- 推定された expert のうち `slot < 0` のものだけを CPU lane 候補として記録し、各後続 layer で `DS4_LA_MAX` 件を上限にします。`DS4_LA_MAX` 未設定時の上限は 4 です（`src/dsv41/ds4_model.cu:6612-6622`）。
- `DS4_LA_THREADS` 未設定時は helper thread を 3 本作ります。設定時は `atoi` の結果回数だけ thread を作るため、0 以下なら worker は作られません（`src/dsv41/ds4_model.cu:6558-6562`）。これらは先読み処理の実行量に関わる別変数です。

## 実行時の詳細

`la_depth()` 内の `static const int d` は、初回に `la_depth()` が呼ばれた時点の環境値を保存します。`la_enabled()` は距離が正かを返し、decode path は距離 1..2 の各 layer について、現在の layer の入力 `d.x` と後続 layer の router weight/bias で gate と route を計算し、expert index を host にコピーします。route 結果は `h_idx_a` に保持されます（`src/dsv41/ds4_model.cu:6550-6553,10433-10447`）。

現在の layer の CPU lane expert を組み立てた後、`lookahead_prefetch()` は `ev2` を同期し、後続 layer ごとに推定された expert の3行列（`r = 0..2`）を `LaPool` の queue に追加します。helper thread は `mincore` で該当ページの常駐状況を調べ、cold と判定した範囲について `os::prefetch` を呼びます。queue が 64 件を超える場合は古い要求を捨てます（`src/dsv41/ds4_model.cu:6555-6587,6592-6623`）。

環境値を読む箇所はこの一箇所です。`DS4_LOOKAHEAD` 自体によるログ、無効値警告、終了コード変更は見つかりません。`DS4_CPU_LOG` が有効な場合は終了時に `lookahead: ...` の集計を stderr に出す登録が行われます（`src/dsv41/ds4_model.cu:6600-6604`）。`cudaEventSynchronize(ev2)`、`mincore`、`os::prefetch` の戻り値をこの処理は検査していません（`src/dsv41/ds4_model.cu:6611,6576-6580`）。

## 根拠

- 読み取り、未設定時の 0、`atoi`、上限 2、static cache: `src/dsv41/ds4_model.cu:6550-6553`。
- Metal guard と単一 token 条件: `src/dsv41/ds4_model.cu:6544-6553,10432-10448,10527-10529`。
- 後続 layer の対象条件と expert 推定: `src/dsv41/ds4_model.cu:10433-10447`。
- CPU lane expert の選別、worker queue、prefetch、終了時集計: `src/dsv41/ds4_model.cu:6555-6623`。

コメントには「default 2」とありますが、同じ箇所の実装は未設定時に 0 を返します。実装コメントにも「off by default until it is measured faster」とあるため、コードに従い未設定時は無効として記載しました（`src/dsv41/ds4_model.cu:6549,6552`）。
