# `DISPLAY`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリや GPU ドライバーが読む `DISPLAY` の意味は対象外。

## 役割

Strata の setup と HTTP サーバーが、Linux 上でグラフィカルなデスクトップセッションがあるかを判定するために参照します。単独で VRAM 予約量やエンジン設定を変更する値ではありません。判定結果により、AMD HIP 利用時に VRAM を多めに空けるよう勧める案内が表示されることがあります。

## 値と判定

Strata は値の形式を parse せず、Python の `bool(env.get("WAYLAND_DISPLAY") or env.get("DISPLAY"))` で判定します。

| 状況 | 判定 |
|---|---|
| `DISPLAY` が未設定、または空文字で、`WAYLAND_DISPLAY` も未設定か空文字 | デスクトップなし |
| `DISPLAY` が空でない文字列で、`WAYLAND_DISPLAY` が未設定か空文字 | デスクトップあり |
| `WAYLAND_DISPLAY` が空でない文字列 | デスクトップあり。OR の短絡評価により `DISPLAY` の値は判定に不要 |

従って `DISPLAY=0` や任意の非空文字列も真として扱われます。空白だけの値も非空なので真です。`DISPLAY` だけが設定されていても、OS 条件を満たさなければデスクトップありとは判定しません。

## 有効になる条件

- `setup.py` の判定は `sys.platform.startswith("linux")` の場合に限ります。setup の AMD HIP 経路では、`--vram-reserve-mib` の明示指定がなく、小型カード向け案内にも入らない場合に、デスクトップ向け 3072 MiB 予約の案内を表示します。これは推奨文であり、設定や引数は変更しません。
- `serve/server.py` の判定は `os.name != "nt"` かつ `sys.platform != "darwin"` の場合に限ります。通常の単一エンジン起動後、HIP backend で、報告された空き VRAM が整数かつ 2048 MiB 未満、現在の `--vram-reserve-mib` が 3072 MiB 未満（未指定なら 700 MiB として扱う）なら、同じ 3072 MiB 予約を勧める note を表示します。GPU replica groups がある場合、この note 判定は呼ばれません。
- NVIDIA 向け setup の案内は `DISPLAY` 判定を使いません。`nvidia-smi` の `display_active` が `Enabled` かを別途確認します。

## 実行時の詳細

両 Python 関数は引数 `env` が渡されなければ、その呼び出し時点の `os.environ` を参照します。setup 側の `linux_desktop()` は `setup.py:5717-5719` で案内の要否を決める際に呼ばれます。サーバー側はエンジン起動後の `server.py:6428-6432` で判定し、条件を満たすと標準出力へ `[strata] note: ...` を出します。環境変数を起動後に変更した場合の再評価は、これらの関数が次に呼ばれた時点の環境に依存します。

## 根拠

- `setup.py:4634-4637` — Linux 限定の `WAYLAND_DISPLAY` / `DISPLAY` 判定。
- `setup.py:5712-5722` — AMD HIP setup でのデスクトップ案内と、NVIDIA の別判定。
- `setup.py:849-853` — NVIDIA は `nvidia-smi display_active` を使う。
- `serve/server.py:5852-5855` — サーバー側の OS 条件と同じ環境変数判定。
- `serve/server.py:5858-5875,6428-6432` — 空き VRAM・reserve 条件、表示文字列、呼び出し位置。
- `docs/DETAILS.md` には `--vram-reserve-mib` のエンジン側の挙動や例がありますが、`DISPLAY` を使ったデスクトップ検出の説明は見当たりません。ここでは測定値を主張せず、現行ソースの案内条件のみを記載しました。
