# `ALLOW_UNKNOWN_BUILD_ID`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Windows 用 `packaging/build_dsv41_windows.bat` が、ビルドした `strata-dsv41.exe --version` の出力に `build unknown` が含まれたとき、ビルドを失敗扱いにする検査を許容するための環境変数です。Strata の通常実行時に読み取る設定ではなく、このバッチによるビルド後検査にだけ使われます。

## 値と判定

バッチは `%ALLOW_UNKNOWN_BUILD_ID%` を文字列 `1` と比較します。数値変換や真偽値 parse はありません。

| 状態・値 | `build unknown` が出力された場合の扱い |
|---|---|
| 未設定 | 空文字に展開され、許容しない。エラーを表示して終了コード 1 |
| 空文字 | 許容しない。未設定と同じ |
| `1` | 許容する。検査を通過して `built ...` を表示し、バッチは終了コード 0 で終了 |
| `0`、`true`、`01`、`1x` など `1` 以外 | 許容しない。エラーを表示して終了コード 1 |

版情報に `build unknown` が含まれない場合、この変数の値にかかわらず当該検査は失敗しません。比較はバッチ中の引用符付き文字列比較で、部分一致や数値としての評価ではありません。

## 有効になる条件

- `packaging/build_dsv41_windows.bat` を Windows で実行し、ビルド後の `strata-dsv41.exe --version` 出力に `build unknown` が含まれる場合にだけ判定されます。
- `strata-dsv41` の build ID は、CMake の `STRATA_BUILD_ID` が未指定ならソースツリーの `BUILD_ID` ファイル、次に Git の短縮 commit ID、いずれも得られない場合は `unknown` になります。`ALLOW_UNKNOWN_BUILD_ID` は build ID を設定・変更せず、ビルド後の失敗判定だけを変えます。
- バッチは configure、build、実行ファイル存在確認の各段階で先に失敗した場合は、終了コード 1 で終了します。したがって本変数はそれらの失敗を許容しません。

## 実行時の詳細

バッチは `strata-dsv41.exe --version` の出力行を `DSV41_VERSION` に取り込み、まずその値を表示します。次に `DSV41_VERSION` から `build unknown` を取り除いた値が元の値と異なるかを調べます。含まれている場合に限り、`ALLOW_UNKNOWN_BUILD_ID` が厳密に `1` でなければ `strata-dsv41.exe prints no commit: build from a git checkout or put the commit in BUILD_ID` と表示して `exit /b 1` します。検査を通れば `built <build dir>\strata-dsv41.exe` を表示して `exit /b 0` します。

そのため、未設定・空文字・`1` 以外の値では、unknown ID の実行ファイル自体が作られていてもバッチの成功条件を満たしません。`1` はその検査だけを通過させます。読み取りはバッチ実行中の検査時に行われます。実行ファイル起動時に環境が継承される可能性はありますが、この名前の参照はバッチの条件式だけで、Strata の実行ファイルによる読み取りは確認できません。

## 根拠

- `packaging/build_dsv41_windows.bat:23-31` — 古い実行ファイルを削除してビルドし、`--version` 出力を確認した後に変数を厳密比較する処理、表示文言、終了コード。
- `CMakeLists.txt:918-932` — DSV41 実行ファイルの生成と build ID の選択・`unknown` fallback。
- `src/dsv41/ds4_main.cpp:1364-1366` — `--version` が `strata-dsv41 <version> build <DS4_BUILD_ID>` を出力して終了する処理。
- `packaging/README.md:38-42` — DSV41 エンジンの Windows ビルド手順としてこのバッチを案内。
- `000_envvers.md:34` — 候補一覧に名前がある。Strata ソース内での完全一致参照は `packaging/build_dsv41_windows.bat:30` のみで、C++/Python の実行時環境読み取りは確認できなかった。
