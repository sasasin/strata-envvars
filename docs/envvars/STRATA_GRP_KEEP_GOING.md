# `STRATA_GRP_KEEP_GOING`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`gr_parity` の fused GR / QFUSE 二グループ検証で、比較失敗が起きた後も反復を続けるための診断用フラグです。通常の Strata 推論・サーバー設定ではなく、CUDA カーネル検証プログラム専用です。`gr_parity` は CMake のテスト実行ファイルとして登録されています（`src/kernels/gr_parity.cpp:278-282,464-473`、`CMakeLists.txt:1384-1387`）。

## 値と判定

値の内容は parse されず、`std::getenv()` が null かどうかだけを見ます。空文字を含め、環境変数が存在すれば有効です。

| 環境の状態 | `keep_going` | 動作 |
|---|---:|---|
| 未設定 | `false` | 二グループ比較で失敗を記録した後、次の反復条件で検証を止める |
| 任意の値（`1`, `0`, `false` など） | `true` | 失敗を記録しながら反復を続ける |
| 空文字 | `true` | 変数が設定済みなので反復を続ける |

したがって `=0` や `=false` も無効化ではありません。明示的に止めるには変数を unset にします。判定結果は `fused_multi_lds_parity()` の呼び出し時に通常のローカル `const bool` として一度取得されます。関数は `main()` から一度呼ばれるため、プロセス実行中の値変更を再読込する経路はありません（`src/kernels/gr_parity.cpp:473,949`）。

## 有効になる条件

- `gr_parity` を実行し、fused multi 反復検証まで到達すること。CMake は `gr_parity --selftest` をテストとして登録しています（`CMakeLists.txt:1384-1387`）。このプログラムは CUDA runtime を include し、デバイス上の比較を行います（`src/kernels/gr_parity.cpp:22-26,278-282`）。
- `STRATA_GR_V3` が無効であること。`main()` は同変数が未設定なら `0` を設定し、`fused_multi_lds_parity()` は `atoi(v) != 0` を static cache します。V3 が有効なら `if (!v3)` の二グループ検証ブロックごと実行されず、この変数は読み取られません（`src/kernels/gr_parity.cpp:340-342,470-473,611-617`）。
- CLI 引数にこのフラグを上書きする指定はありません。受け付ける引数は `--selftest` のみで、その他は usage を stderr に出し終了コード 2 で終了します（`src/kernels/gr_parity.cpp:618-622`）。

`STRATA_GRP_REPS` は別の環境変数で、二グループ検証の反復数を指定します。`STRATA_GRP_KEEP_GOING` 自体はその回数や比較内容を変更しません（`src/kernels/gr_parity.cpp:471-474,509`）。

## 実行時の詳細

この判定は、`T=2..8` の二グループ分割を行い、各 `T` について直接実行・graph replay の結果を参照量子化結果と比較するテストに適用されます。比較差、書き越し、カウンタ残留などは `g2bad` に加算され、該当内容が stdout に表示されます。フラグ unset 時は `g2bad` が非ゼロになると反復ループの条件を満たさなくなり、設定時は反復を続けて追加の失敗を数えます（`src/kernels/gr_parity.cpp:487-509,532-589`）。

継続フラグは失敗を成功扱いにしません。最後に失敗数と `FAIL` を stdout に出し、`bad` が非ゼロならプロセスは終了コード 1 を返します。CUDA API エラーは `check()` がエラー文字列を stderr に出して即時に終了コード 1 とする別経路です（`src/kernels/gr_parity.cpp:39-44,587-606,955-959`）。

## 根拠

- 唯一の環境読み取りと反復条件: `src/kernels/gr_parity.cpp:470-509`。
- 失敗の記録・出力と終了コード: `src/kernels/gr_parity.cpp:532-589,955-959`。
- 実行ファイルと CTest 登録: `CMakeLists.txt:1384-1387`。
