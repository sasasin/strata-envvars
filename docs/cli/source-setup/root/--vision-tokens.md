# `--vision-tokens`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、更新 wrapper から委譲） |
| オプション | `--vision-tokens N` |
| 別名 | なし |
| 値 | 画像1枚あたりの画像 token 数を表す正の整数。1以上、上限は parser で定められていない |

## 役割

画像読み取りを有効にしたモデルについて、画像 encoder が画像1枚を処理するときの `vision.max_tokens` を指定する。小さい文字や図表を読み取れる量に関わり、値を増やすと画像 encoding に時間がかかることがある。setup は GPU encoder の既定値を1024、CPU encoder の既定値を300にする（`setup.py:797-798`、`setup.py:8442-8445`）。

## 使い方

```sh
./setup.sh --vision cpu --vision-tokens 768
```

Windows では、例えば `START-HERE.bat --setup --vision gpu --vision-tokens 2048` と指定できる。wrapper は引数を `setup.py` に渡す（`setup.sh:12,76`、`START-HERE.bat:48,53`）。

## 値と既定値

- 値は `argparse` の `type=int` で整数に変換され、1未満は `ap.error` で拒否される。上限値の検証はない（`setup.py:8442`、`setup.py:8567-8568`）。整数に変換できない値は `argparse` の引数エラーになる。
- 指定を省略すると GPU encoder は1024、CPU encoder は300。既存モデルを再 setup する場合は、同じ encoder 種別の既存 `vision.max_tokens` が正の整数で既定値と異なれば、それを引き継ぐ。明示した `--vision-tokens` は既存値より優先される（`setup.py:6899-6913`）。
- 既存値の引き継ぎは既存設定の `vision.gpu` が現在選ばれた encoder と一致する場合に限る。encoder 種別が変わればその種別の既定値に戻る（`setup.py:6904-6913`）。

## 実行時の動作

画像読み取りが有効な場合、setup は値を生成する実行設定 JSON の `vision.max_tokens` に保存する。通常の Linux/Windows 経路では新規または既存のモデル設定に記録し（`setup.py:7694-7703`、`setup.py:9697-9707`）、Mac の Control 経路でも同じ設定項目を作る（`setup.py:8396-8402`）。既存設定を書き換える際、内容が変われば `.bak` に旧設定をコピーしてから新設定を書き込む（`setup.py:6312-6340`）。

サーバーはこの設定値を vision reader の `--max-tokens` 引数に渡す。画像 token 数が設定値を超えても最大12.5%の丸め余地までは通し、それを超えた画像は reader が拒否する（`serve/server.py:2624-2649`、`tools/vision/strata_vision.cpp:316-319,333-334`）。したがって設定値は無制限に受け付けられる一方、過大な値は画像読み取りに必要な資源や時間を増やし得る。CPU encoder で既定値を超えると時間がよりかかる旨を setup が表示し、GPU encoder でGPU既定値1024を超える場合はVRAMと context をより使う旨を表示する（`setup.py:6914-6920`）。これは案内であり値を上限に切り詰めない。

## 適用条件と副作用

- `--vision` 等によって画像読み取りが有効である場合に設定値が使われる。画像読み取りが `none`（off）の場合、値は使われず `--vision-tokens: images are off...` の警告が出る（`setup.py:7704-7707`、`setup.py:9706-9709`）。
- Intel SYCL 経路は引数を `setup.py` の parser に戻すため同じ検証・設定経路を使う（`sycl/setup_intel.py:547-554`）。
- Apple Silicon の通常のソース setup は `setup.py` から `metal/setup_mac.py` に引数を委譲する。そちらは `--vision-tokens` を定義せず、未知引数として警告し、画像設定は固定の1024を使うため、このオプションは反映されない（`setup.py:7314-7318`、`metal/setup_mac.py:328-356,535-538`）。Mac の Control setup は `setup.py` 本体の parser と `mac_control_setup` を通るため、設定値を利用する（`setup.py:8561-8562,8396-8402`）。
- setup はモデルの実行設定 JSON を更新する。値を明示した場合でも実行エンジンへの `--vision-tokens` 引数転送はせず、設定の `vision.max_tokens` として reader 起動時に利用する（`setup.py:7697-7703,9699-9705`、`serve/server.py:2640-2649`）。

## 出力とエラー

- 明示値または既存設定から引き継いだ値がある場合、setup は採用値と encoder の既定値を含む案内を表示する。新規設定で値を省略したときは既定値が使われるが、この案内行は出ない（`setup.py:6903-6920`）。画像がoffなら未使用の警告を表示する（`setup.py:7706-7707,9708-9709`）。
- 1未満、または整数でない値は setup の引数エラーとなる。1未満の場合は「1 or more」の説明を付けた usage error で終了する（`setup.py:8567-8568`）。
- 実行時に reader が画像 token 数の超過を検出した場合、reader は `ERR` と超過数・上限を出力し、その画像を拒否する（`tools/vision/strata_vision.cpp:316-319,333-334`）。サーバーから利用者へ返す具体的な HTTP エラー内容・status はこの調査では特定していない。
- 通常のソース setup を行う macOS では、未知引数として警告され値が使用されない。これは `setup.py` の通常 parser の validation より先に Mac 専用 parser に委譲されるため（`setup.py:8418-8419`、`metal/setup_mac.py:356-359`）。

## 根拠

- parser・整数型・help 記述: `setup.py:8439-8445`
- 1以上の validation: `setup.py:8553-8568`
- encoder 別既定値、既存設定からの引き継ぎ、案内: `setup.py:797-798,6899-6921`
- 通常 setup の設定生成と images off の警告: `setup.py:7694-7707,9697-9709`
- Mac Control setup の設定生成: `setup.py:8396-8402`
- 既存設定の backup と書き込み: `setup.py:6312-6347`
- reader 引数への反映と画像超過判定: `serve/server.py:2624-2649`、`tools/vision/strata_vision.cpp:316-334`
- source setup の Mac 委譲・専用 parser: `setup.py:7314-7318`、`metal/setup_mac.py:328-359,535-538`
- Intel SYCL の再委譲: `sycl/setup_intel.py:547-554`
