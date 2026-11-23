# `DYLD_LIBRARY_PATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata 本体の C++ engine が読む設定ではなく、macOS で Strata の Python コードが engine 子プロセスを起動するとき、その子プロセス用環境に既存値を引き継ぎ、engine package のライブラリフォルダーを前置するために使う。参照は `local_engine._version_of`、shape engine の起動確認、Hy4 / Inkling の機能 probe、engine 更新時の smoke check、tokenizer export にある（`terminal/strata_control/local_engine.py:48-55`、`terminal/strata_control/shape_engine.py:217-228`、`terminal/serve/hy4_kind.py:70-96`、`terminal/serve/inkling_kind.py:60-92`、`terminal/strata_control/updater.py:1013-1027`、`terminal/setup.py:10129-10139,10514-10524`、`terminal/serve/server.py:8596-8612`）。

変数自体の値で engine の設定、GPU 選択、モデル処理を切り替えるコードはない。Strata が変えるのは子プロセスへ渡すライブラリ検索パスだけである。これらの箇所で `DYLD_LIBRARY_PATH` が選ばれるのは `sys.platform == "darwin"`（または Windows 以外かつ Darwin）である場合。Windows では `PATH`、他の OS では `LD_LIBRARY_PATH` を選ぶ（同上）。

## 値と判定

値の内容を `DYLD_LIBRARY_PATH` 自身で parse・検証する処理はない。macOS の各該当経路は `dict(os.environ)` で環境を複製し、`env.get(var)` で既存値を参照して、新しいライブラリフォルダーと `os.pathsep` で連結している。したがって未設定と空文字は、追加先がある場合にはどちらも「既存値なし」として扱われる。空でない既存値は文字列のまま後ろに残り、空白・不正なパス・複数要素の妥当性は Strata 側で検査されない。先頭文字・真偽文字列・数値としての意味も持たない。`DYLD_LIBRARY_PATH` の値だけを変更する専用 fallback や clamp はない（`terminal/strata_control/local_engine.py:50-54`、`terminal/strata_control/shape_engine.py:222-228`、`terminal/strata_control/updater.py:1018-1027`、`terminal/serve/server.py:8607-8612`）。

| 条件 | 未設定 | 空文字 | 非空値（例） | 境界・無効値 |
|---|---|---|---|---|
| macOS で、該当する子プロセス用ライブラリフォルダーがある | 追加フォルダーだけを設定 | 追加フォルダーだけを設定 | 追加フォルダーを先頭にし、元の文字列を後ろに連結 | `0`、`true`、空白を含む値なども parse せず、そのまま連結 |
| 追加フォルダーがない経路 | 環境複製時の未設定状態 | 空文字のまま | 元の値をそのまま保持 | 値の妥当性検査なし |
| Windows / macOS 以外 | この名前は選ばれない（`PATH` / `LD_LIBRARY_PATH` を使用） | 同左 | 同左 | `DYLD_LIBRARY_PATH` の値はこの目的では参照されない |

値を有効・無効と判定する形式はない。既存値が非空かどうかだけが連結の形を決める。追加フォルダーの有無は経路ごとに異なり、shape probe / Hy4・Inkling probe は設定中の `lib_dirs` のうち存在するディレクトリーがある場合に追加し、更新 smoke と local engine の version 確認は package フォルダーを追加する。tokenizer export は engine の親フォルダーを追加する（`terminal/strata_control/shape_engine.py:222-228`、`terminal/serve/hy4_kind.py:84-91`、`terminal/serve/inkling_kind.py:74-87`、`terminal/strata_control/updater.py:1018-1027`、`terminal/strata_control/local_engine.py:48-55`、`terminal/setup.py:10129-10139,10514-10524`、`terminal/serve/server.py:8604-8612`）。

## 有効になる条件

- macOS 上で、次のいずれかの Strata 操作が対応する子プロセスを起動すること。
- local engine の追加では、`strata components add-build` が候補 engine の `--version` を確認する場合に使用する。engine が 10 秒以内に応答しない、起動できない、または非ゼロ終了する場合は `AddBuildError` となり、追加を拒否する（`terminal/strata_control/local_engine.py:48-69,127-145`）。
- shape engine の導入・更新では、stage 済み engine の起動確認で使用する。失敗時はパッケージを削除し、理由を含む update error とする（`terminal/strata_control/shape_engine.py:217-247,313-334`）。
- Hy4 / Inkling の server 側 `--info` probe では、モデル引数と実行ファイルがあり、同じ実行ファイル・モデル（および Inkling では vision / dspark 引数）に対する probe 結果が未 cache の場合に使用する。probe は結果を `_PROBES` に保存する（`terminal/serve/hy4_kind.py:70-96`、`terminal/serve/inkling_kind.py:60-92`）。
- 更新確認では、モデルがない、対象 engine に合うモデルがない、またはメモリー不足などで model test load を省略する経路の `binary_smoke` が engine の `--version` を起動する際に使う（`terminal/strata_control/updater.py:1013-1027,1342-1391`）。
- Hy4 / Inkling の setup と server の tokenizer 準備では、既存ファイルから tokenizer を作れず、engine が存在する場合に `--export-tokenizer` を試す経路で使う。setup 側は前段で tokenizer ファイルが見つからない場合、server 側は `.strata` モデルで不足 tokenizer を補う場合に限られる（`terminal/setup.py:10120-10139,10500-10529`、`terminal/serve/server.py:8536-8544,8596-8620`）。
- 通常の server engine 起動では、`child_env` が `os.environ` 全体を複製するため、元の `DYLD_LIBRARY_PATH` は環境内にそのまま残り engine subprocess に渡る。一方、engine の `lib_dirs` を前置する変数選択は Windows で `PATH`、それ以外で `LD_LIBRARY_PATH` であり、この経路では macOS 用に `DYLD_LIBRARY_PATH` を選ばない（`terminal/serve/server.py:3870-3916,8279-8307`）。

## 実行時の詳細

各明示的な前置処理は子プロセス用環境を作る時点で `os.environ` を複製し、その時点の `DYLD_LIBRARY_PATH` を参照する。名前を引数で受け取る helper や、この値専用の static cache はない。値は Strata が長期 cache せず、後続の別 invocation はその時点のプロセス環境を複製する。生成済みの `env` は `subprocess.run(..., env=env)` に渡されるため、その子プロセスには前置後の値が渡る（`terminal/strata_control/local_engine.py:50-55`、`terminal/strata_control/shape_engine.py:222-228`、`terminal/serve/hy4_kind.py:84-96`、`terminal/serve/inkling_kind.py:74-92`、`terminal/strata_control/updater.py:1018-1027`、`terminal/setup.py:10132-10139,10518-10524`、`terminal/serve/server.py:8607-8612`）。通常の server engine 起動でも `child_env` は `os.environ` を複製し、生成した環境を engine 起動に渡すので、既存値は変更せず継承される（`terminal/serve/server.py:3870-3916,8279-8307`）。

値の優先順位を比較して Strata の設定を選ぶ仕組みはない。既存の `DYLD_LIBRARY_PATH` を維持しつつ、その操作が必要とする engine 側ディレクトリーを前方に追加する。CLI 引数や他の Strata 環境変数によるこの連結の上書きは確認できない。

観測される結果は各起動確認の結果であり、変数値に対する専用ログはない。local engine の起動失敗は `AddBuildError` の理由になる。shape engine の起動失敗は update error の理由になる。updater の `binary_smoke` は失敗出力を保存できる場合 `.updates/logs` に保持し、`TestStartFailed` の理由を返す。server の tokenizer export は例外を捕捉して後続の候補・取得処理へ進む。server 側で既存 tokenizer から生成した成功ログは `[strata] generated missing tokenizer from {tj} -> {tpath}`、engine export から生成した成功ログは `[strata] exported missing tokenizer via {exe.name} -> {tpath}`（`terminal/serve/server.py:8588-8593,8611-8617`）。これらは子プロセス操作の結果であり、`DYLD_LIBRARY_PATH` 自体の値を示すログではない。setup の export 経路にはこの変数に対する専用ログがない（`terminal/setup.py:10137-10155,10523-10545`）。

## 根拠

- 候補名は `docs/envvars/000_envvers.md:158` にある。Strata 所有コードの完全一致検索では、実装参照は `terminal/setup.py:10133,10519`、`terminal/strata_control/local_engine.py:51`、`terminal/strata_control/shape_engine.py:223`、`terminal/strata_control/updater.py:1018`、`terminal/serve/hy4_kind.py:88`、`terminal/serve/inkling_kind.py:78`、`terminal/serve/server.py:8608`。他の完全一致はテスト内の assertion である。
- 環境複製と子プロセスへの引き渡し: `terminal/strata_control/local_engine.py:50-55`、`terminal/strata_control/shape_engine.py:222-228`、`terminal/strata_control/updater.py:1018-1027`、`terminal/serve/hy4_kind.py:84-96`、`terminal/serve/inkling_kind.py:74-92`、`terminal/setup.py:10132-10139,10518-10524`、`terminal/serve/server.py:8607-8612`。
- 呼び出し結果と失敗処理: `terminal/strata_control/local_engine.py:56-74,127-145`、`terminal/strata_control/shape_engine.py:313-334`、`terminal/strata_control/updater.py:1028-1058,1342-1391`、`terminal/setup.py:10137-10155,10523-10545`、`terminal/serve/server.py:8536-8544,8596-8620`。
- Strata の技術資料 `docs/DETAILS.md` に、この変数の挙動や測定値の記載は見つからなかった。上記は調査対象 commit のソースに基づく。
