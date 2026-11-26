# `CMAKE_BUILD_PARALLEL_LEVEL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata がこの環境変数を読み取って処理を切り替える箇所は見つからなかった。Strata 所有コードで確認できたのは、macOS Metal engine の packaging script が `JOBS` の値をこの名前で export し、後続の子プロセスへ渡す処理である。したがって、既に親環境にある値を Strata が設定として採用する変数ではない。`tools/packaging/mac/build_engine.sh:28,57-58`

## 値と判定

この script は値を数値として parse・検証しない。`JOBS` は初期値 `2` で、コマンドラインの `--jobs N` が指定されるとその文字列に置き換わり、最後に `CMAKE_BUILD_PARALLEL_LEVEL` へそのまま代入・export される。親環境に同名変数が設定済みでも、この代入で上書きされる。`--jobs ""` のような空文字も script 側では拒否されず、値として export される。`tools/packaging/mac/build_engine.sh:28,30-39,57-58`

| script の指定 | export される値 | script 内での判定 |
|---|---|---|
| `--jobs` なし | `2` | 固定の既定値 |
| `--jobs 1` | `1` | 文字列をそのまま転送 |
| `--jobs 0`、負数、非数値文字列、空文字 | 指定文字列 | 値域・数値としての妥当性を検査しない |

これらは Strata script が export する値の規則であり、CMake 等の外部プログラムが値をどう解釈するかはここでは扱わない。

## 有効になる条件

- `tools/packaging/mac/build_engine.sh` の実行時に export される。export 自体は `--stages` の内容にかかわらず行われる。`tools/packaging/mac/build_engine.sh:51-60`
- `engine` stage が含まれると、script は `cmake -S ... -B ...` と `ninja -j"$JOBS"` を起動する。ビルド時の並列数として script が明示的に渡す指定は Ninja の `-j"$JOBS"` であり、Strata のソースコードには `CMAKE_BUILD_PARALLEL_LEVEL` を読み取る処理はない。`tools/packaging/mac/build_engine.sh:60-67`
- `engine` stage がない場合にも変数は export されるが、この script のその実行では CMake と Ninja の engine build コマンドを起動しない。`tools/packaging/mac/build_engine.sh:57-60`

## 実行時の詳細

`--jobs` は引数解析中に `JOBS` へ格納される。version の検査等を通過した後、stage の処理に入る前に `CMAKE_BUILD_PARALLEL_LEVEL` を無条件で export するため、親プロセスから同名変数を変更してもこの script 内の値には反映されない。export 後に起動するプロセスはその環境を継承する。engine stage では CMake の configure コマンドに続き、Ninja を `-j"$JOBS"` 付きで直接起動する。`tools/packaging/mac/build_engine.sh:30-40,51-67`

この export を Strata 自身が読み直す箇所や、実行中に再評価・cache する処理は見つからなかった。CMake configure と Ninja build の失敗時には、それぞれのログ末尾を表示して終了コード `1` で終了する分岐があるが、`CMAKE_BUILD_PARALLEL_LEVEL` 専用の検証・警告・エラー処理ではない。`tools/packaging/mac/build_engine.sh:64-66`

## ログと測定値

この変数の値や妥当性を示す専用ログはない。build コマンドが失敗した場合は CMake configure ログまたは Ninja build ログの末尾 30 行を表示する。`tools/packaging/mac/build_engine.sh:64-66`

## 根拠

- `tools/packaging/mac/build_engine.sh:28-39` — `JOBS=2` と `--jobs` 引数の処理。
- `tools/packaging/mac/build_engine.sh:57-58` — `CMAKE_BUILD_PARALLEL_LEVEL` への無条件代入と export。
- `tools/packaging/mac/build_engine.sh:60-67` — engine stage 条件、CMake configure、Ninja への明示的 `-j` 指定と失敗時の処理。
