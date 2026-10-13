# `STRATA_DUMMY_NODES`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

検証ウィンドウの GPU 処理に、layer/group ごとに空の GPU kernel node を追加する計測用フックです。ソースのコメントは「window 内で node 1 個にかかるコスト」を測る目的としています。モデル計算の結果を変える処理ではなく、追加した kernel は何も読み書きしません。

環境変数を読むのは `Verifier::record_window()` のみです。通常のウィンドウ graph と batch ウィンドウ graph の記録はいずれもこの関数を呼びます。Verifier を使わない実行経路では、この変数は参照されません。

## 値と判定

値は `std::atoi` で `int` に変換され、変換結果を `dummy` として `for (int d = 0; d < dummy; ++d)` の反復回数にします。文字列全体の検証、範囲チェック、clamp はありません。

| 環境変数の状態・値 | 動作 |
|---|---|
| 未設定 | `dummy = 0`。追加しない |
| 空文字 | `atoi` の結果は `0`。追加しない |
| `0`、数値で始まらない文字列 | 結果は `0`。追加しない |
| 正の整数 `k` | 各 layer に `k` 個追加 |
| 負の整数 | 反復条件 `d < dummy` が最初から偽となり、追加しない |
| 数字の後ろに文字が続く値（例: `3x`） | `atoi` が先頭の数値部分を変換し、結果が正ならその数だけ追加 |

`atoi` のため、空白や符号を含む入力も C の整数変換規則に従います。整数型 `int` で表現できない値について、実装はエラー処理をしていないため、その結果は利用できる設定値として保証されません。

## 有効になる条件

- CUDA/HIP verifier の window graph 記録で `record_window()` が実行されること。通常の `capture()` と `capture_batch()` の両方から呼ばれます。
- 変換後の値 `dummy` が正であること。

GPU kernel の実装は `src/kernels/cuda/verify_kernels.cu` にあります。`noop_kernel` は空の kernel body で、1 block・32 thread で launch されます。追加 kernel を持つ graph 以外の経路、たとえば verifier を使わない通常 decode にはこの挿入箇所はありません。

## 実行時の詳細

環境変数の読み取りは関数内 `static const int` の初期化 lambda にあります。このため、値を読むのはプロセス起動時ではなく、最初に `record_window()` が該当箇所へ到達したときです。最初の読み取り後は値がプロセス内でキャッシュされ、環境を変更しても同じプロセスでは再評価されません。最初の graph 記録より前に環境を設定すればその値が使われます。

各 `pre(l, grp)` 呼び出しで、最初の grouped GR read の後に同じ CUDA stream `cs` へ空 kernel を `dummy` 回 enqueue します。制御フローは各 layer について group 数 `G` 回 `pre` を呼ぶため、捕捉された graph に入る追加 node 数は、記録対象の layer 数を `L` とすると `L × G × max(dummy, 0)` です。空 kernel 自体がモデルの tensor や状態を更新することはありませんが、graph の node 数と GPU の実行時間を増やす目的の挿入です。

この変数専用のログや警告はありません。通常の graph capture が失敗した場合には既存の `verify: end capture: ...` または `verify: end batch capture: ...` エラー経路になります。調査した `docs/DETAILS.md` にはこの変数の説明を確認できませんでした。計測値や性能効果を裏付ける文書も見つからなかったため、定量的な効果は記載しません。

## 根拠

- `src/core/verify.cpp:826-835`: `record_window()` の定義。
- `src/core/verify.cpp:1074-1078`: `STRATA_DUMMY_NODES` の唯一の読み取り、`atoi` による変換、layer ごとの launch。
- `src/core/verify.cpp:1846-1863`: 通常 window の graph capture が `record_window()` を呼ぶ。
- `src/core/verify.cpp:2582-2598`: batch window の graph capture が `record_window()` を呼ぶ。
- `src/core/verify.cpp:1688-1694`: 各 layer の `pre(l, grp)` が group ごとに呼ばれる。
- `src/kernels/cuda/verify_kernels.cu:1340-1343`: 空の `noop_kernel` と 1 block・32 thread の launch。
- `include/strata/kernels/verify_kernels.hpp:57-58`: `gpu_noop` の宣言と計測意図のコメント。
