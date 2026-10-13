# `STRATA_RSS_TRACE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

`strata generate` / `strata serve` の初期化中に、プロセスの `/proc/self/status` から `RssFile` を読み、stderr に GiB 表示する診断用スイッチです。CUDA 版と SYCL 版の `generate.cpp` に同じ実装があります。環境変数は計測処理を有効にするだけで、モデル読み込み、arena 解放、prefetch、GPU 実行の選択は変えません。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | 計測しない |
| 空文字を含む何らかの値が設定済み | 計測する |

値の文字列、数値、大文字小文字は parse しません。`std::getenv(...) != nullptr` の設定有無だけで判定します。その判定は `rss_probe()` の最初の呼び出し時に `static const bool` として保存され、以後同じプロセス内では再評価されません。最初の呼び出し後に環境を書き換えても動作は変わりません。

## 有効になる条件

`rss_probe()` は CUDA と SYCL の生成コードにあります。Linux の `/proc/self/status` を開く実装で、ファイルを開けない環境では何も出力しません。したがって環境変数を設定しても `/proc` が利用できなければ観測結果はありません。

呼び出し箇所は、expert arena の解放前・解放後・prefetch hint 後、serve の prompt path 初期化後、および serve 起動時に VRAM 空きが 256 MiB 以上と報告された場合の `serving` 記録です。各パスに到達しない場合、その地点の記録も出ません。

## 実行時の詳細

計測時は `/proc/self/status` を読み、`RssFile:` で始まる行を探します。行が見つかるとコロン以降を `atoll` で数値化し、KiB 値を `1024 * 1024` で割って GiB として、次の形式で stderr に出力して flush します。

```text
strata rss: <地点>: RssFile <値> GiB
```

これはプロセス全体の file-backed resident memory の値です。arena だけを識別して測る実装ではありません。`RssFile:` 行が見つからない場合は初期値 `-1` のまま表示され得ます。`/proc/self/status` を開けなかった場合は静かに return します。この関数は測定値に基づく分岐やエラー終了を行いません。

## 根拠

- `src/program/generate.cpp:229-242` と `sycl/src/program/generate.cpp:271-284`: 設定有無の判定、`/proc/self/status` の読み取り、単位変換、stderr 出力。
- `src/program/generate.cpp:6193-6212` と `sycl/src/program/generate.cpp:5842-5861`: arena 解放・prefetch の前後での呼び出し。
- `src/program/generate.cpp:7259,9035` と `sycl/src/program/generate.cpp:6811,8440`: prompt path 初期化後と serve 起動時の呼び出し。`serving` の呼び出しは GPU 空き容量が 256 MiB 以上の分岐内。
- `docs/DETAILS.md` と関連ドキュメントには `STRATA_RSS_TRACE` の説明は見つかりませんでした。上記は対象 HEAD のコードに基づく記述です。
