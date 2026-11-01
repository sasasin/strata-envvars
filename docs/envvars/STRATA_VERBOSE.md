# `STRATA_VERBOSE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

セットアップで DeepSeek V4.1 用エンジン `strata-dsv41` が見つからないとき、開発者向けのビルド方法を示す追加案内を出します。エンジンを見つけたりビルドしたりする設定ではなく、セットアップの失敗や終了コードも変えません。読み取り箇所は `setup.py` のみで、エンジン本体や通常の生成処理が読むものではありません。

## 値と判定

| 値 | 追加案内 |
|---|---|
| 未設定 | 出さない |
| 空文字 | 出さない |
| 文字列 `1` | 出す |
| その他すべて（`0`、`true`、`01`、空白を含む値など） | 出さない |

`os.environ.get("STRATA_VERBOSE") == "1"` による文字列全体の完全一致です。数値変換、trim、大文字小文字変換、範囲判定はありません。明示設定値がこの判定の既定値を変える別の設定や CLI オプションはありません。`setup.py` は別条件として `"--verbose" in sys.argv` も検査しますが、通常の CLI 引数解析では `--verbose` が登録されておらず、`parse_args()` が未認識引数として先に拒否します（下記参照）。

## 有効になる条件

この判定は `install_dsv41()` が `exe is None` になった場合だけ実行されます。同関数は DeepSeek V4.1（`MULTI_FILE_FAMILIES`）のセットアップ経路です。エンジンが見つかった場合はこの環境変数を読みません。通常の CUDA/HIP セットアップまたは Control の Mac 用 DeepSeek セットアップがこの経路へ到達します。非 Control の macOS は `main()` 冒頭で別のセットアップスクリプトへ委譲するため、この箇所を通りません。backend やモデルの通常の推論時の挙動は制御しません。

## 実行時の詳細

`install_dsv41()` は `STRATA_DSV41_EXE` などを使った実行ファイルの解決を試し、その後も `exe` が `None` のままなら `STRATA_VERBOSE` をその場で一度読みます。値はキャッシュされず、子プロセスへ転送もされません。値が厳密に `1` のとき stdout に次の案内を追加します。

> Details for developers: build it with cmake -DSTRATA_BUILD_DSV41=ON -DCMAKE_CUDA_ARCHITECTURES=<your card: 86 RTX 30, 89 RTX 40, 120 RTX 50> and point STRATA_DSV41_EXE at it (docs/DEEPSEEK41.md, "Building the engine for your card").

その直後、値にかかわらず `fail()` がエンジン不在の説明と手動手順を stdout に出し、`sys.exit(1)` で終了します。したがって `STRATA_VERBOSE=1` は失敗を回避せず、追加の案内だけを表示します。

`--verbose` はこの条件式に含まれていますが、`main()` の `argparse` 定義にオプション登録がなく、エンジン探索より前の `parse_args()` が未知引数を拒否します。そのため、通常の `setup.py --verbose ...` 起動でこの追加案内を有効にすることはできません。別コードが `sys.argv` を変更して `install_dsv41()` を直接呼ぶ場合の挙動は、この通常 CLI の経路とは区別されます。

## 根拠

- `setup.py:8492-8497` — DeepSeek V4.1 専用の `install_dsv41()`。
- `setup.py:8620-8644` — エンジン探索後、`exe is None` のときの完全一致判定、追加案内、失敗処理。
- `setup.py:887-909` — `say()` は flush 付きの標準出力、`fail()` は説明を出して終了コード 1 で終了。
- `setup.py:9207-9212` — backend オプションまでの parser 定義と `parse_args()`。`--verbose` の登録はありません。
- `setup.py:9218-9225, 9613-9618` — inspect / Mac / SYCL の分岐、および DeepSeek V4.1 セットアップの呼び出し経路。
- `docs/DEEPSEEK41.md:167-186` — 開発者向けエンジンビルド手順。追加案内が指す説明先。
