# `WAYLAND_DISPLAY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata はこの変数を Wayland の接続先として利用したり、値をエンジンに渡して動作を切り替えたりはしません。Python のセットアップとサーバーが、`DISPLAY` と合わせて「Linux のグラフィカルデスクトップがあるか」を判定し、AMD/HIP の VRAM 予約を勧める条件に使います。また、デスクトップアプリの診断ログは設定されている値を「Graphics session」欄に記録します。

## 値と判定

| 読み取り箇所 | 未設定 | 空文字 | 非空文字列 | 判定結果 |
|---|---|---|---|---|
| `setup.py` の `linux_desktop()` | `DISPLAY` も未設定または空なら false | `DISPLAY` が非空でなければ false | true | `sys.platform.startswith("linux")` も必要。どちらか一方が truthy ならデスクトップあり |
| `serve/server.py` の `linux_desktop()` | `DISPLAY` も未設定または空なら false | `DISPLAY` が非空でなければ false | true | `os.name != "nt"` かつ `sys.platform != "darwin"` も必要。どちらか一方が truthy ならデスクトップあり |
| デスクトップ診断ログ | 出力しない | `WAYLAND_DISPLAY=` として出力 | 変数名と値を出力 | Rust の `std::env::var` が成功した場合に記録。非 Unicode 値など `var` がエラーになる値は出力しない |

Python 側は `bool(env.get("WAYLAND_DISPLAY") or env.get("DISPLAY"))` で判定します。文字列の値を parse せず、空文字だけが偽になります。`0`、`false`、空白だけの文字列を含め、空でない値は真です。大小文字や値の形式は検証しません。`DISPLAY` は同じ判定への代替入力です。優先順位はなく、どちらか一方が非空なら真です。数値変換、clamp、無効値時の fallback はありません。

## 有効になる条件

- **セットアップ:** `setup.py` の処理が Linux 上で HIP backend を選び、`--vram-reserve-mib` が指定されていない場合に判定されます。デスクトップありなら 3072 MiB を空けるための再セットアップ用コマンドを案内します。これは助言で、現在の設定や起動引数を書き換えません。明示された `--vram-reserve-mib` があれば、この助言条件から外れます。参照: `setup.py:7504-7519,10282-10284`。
- **サーバー:** 通常の単一エンジン経路で、GPU groups / layer split を使わず、設定 backend が `hip` のときに判定されます。さらにモデル起動後の空き VRAM が整数で 2048 MiB 未満であり、エンジン引数の予約値が 3072 MiB 未満である場合だけ案内文が生成されます。予約値はエンジン引数から整数変換し、引数がない場合は 700、値を整数にできない場合も 700 として扱います。予約値が 3072 MiB 以上なら案内しません。案内は推奨で、設定や引数を変更しません。参照: `serve/server.py:8223-8250,9273-9285`。
- **デスクトップ診断ログ:** `graphics_environment()` が呼ばれる時点のプロセス環境を参照します。保存ログの `Graphics session` 欄と、ウィンドウ crash report の同欄に含まれます。参照: `apps/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-320`。

## 実行時の詳細

セットアップ・サーバーの関数は `env` 引数が省略されたときに `os.environ` を使い、関数呼び出し時に値を読みます。static cache はありません。実際のセットアップとサーバーからの呼び出しは引数を渡さず、それぞれ `setup.py:10282-10284`、`serve/server.py:9282-9285` にあります。したがって、呼び出し時点で環境値が変わっていればその値で判定します。別の環境変数 `DISPLAY` が代替になり、CLI の予約値は上記の案内条件を抑止しますが、`WAYLAND_DISPLAY` による優先上書きはありません。

診断ログ側は `NAMES` の各名前を `std::env::var` で個別に読み、成功したものだけ `  WAYLAND_DISPLAY=<値>` の形式で収集します。ログ保存時または crash report 作成時に呼ばれ、起動時に値を cache する実装ではありません。未設定・取得不能なら該当行がなく、空文字なら空の値を伴う行が入ります。参照: `apps/desktop/src-tauri/src/desktoplog.rs:186-194,256-259,310-320`。

この変数によるログ、警告、終了、失敗の経路はありません。Python の条件が成立して他の VRAM 条件も満たすときは、セットアップが `./setup.sh --vram-reserve-mib 3072` の推奨行を表示し、サーバーは `[strata] note: ...` を標準出力に表示します。診断ログでは環境値を保存します。これらはいずれも案内・記録であり、変数の値そのものが予約 VRAM やエンジンの動作を変更するものではありません。参照: `setup.py:7514-7520,10282-10284`、`serve/server.py:8246-8250,9282-9285`。

## 根拠

- `setup.py:7508-7511` — Linux 判定と `WAYLAND_DISPLAY` / `DISPLAY` の truthiness 判定。
- `setup.py:10282-10284` — HIP かつ予約値未指定時の助言表示。
- `serve/server.py:8227-8230` — サーバー側の OS 判定と truthiness 判定。
- `serve/server.py:8233-8250,9282-9285` — VRAM 条件、予約値 fallback、案内文表示。
- `apps/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-320` — 環境値の収集と診断ログへの記録。

`docs/envvars/000_envvers.md:1701` に候補名があります。候補一覧以外に、`docs/DETAILS.md` のこの変数固有の説明は見つかりませんでした。
