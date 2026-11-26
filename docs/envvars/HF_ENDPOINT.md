# HF_ENDPOINT

調査対象: Strata main の HEAD d46f5f268f8ed797e83a5c63a69bffbd7a581cf6（2026-11-25 時点）。

## 役割

Hugging Face を参照する一部の Strata のダウンロード URL のホストを、環境で指定したホストへ置き換える。setup の pinned revision ファイル・画像生成用ファイル、MTP draft layer、picture reader、DFlash2 drafter、デスクトップ画像モデル API、同梱の調査ツールにそれぞれ読み取り箇所がある。Strata 全体の Hugging Face URL を一括で置き換える設定ではなく、通常の GGUF family shard 等にはこの値を使わない取得経路がある。主な実装は terminal/setup.py の hf_endpoint()、strata_control.pictures.Projector.url()、strata_control.drafting.base_url()、strata_control.transfer._hf_host()、app/host/server/image-models.mjs（terminal/setup.py:129-137, 3947-3948, 6003-6008; terminal/strata_control/pictures.py:72-75; terminal/strata_control/drafting.py:241-249; terminal/strata_control/transfer.py:220-251; app/host/server/image-models.mjs:35-46, 87-91）。

## 値と判定

setup、pictures、drafting、デスクトップ画像モデルは、値を文字列として URL の先頭へ連結し、strip() で前後の空白を除去、rstrip("/") で末尾の / をすべて除去する。未設定、空文字、空白だけ、除去後に空になる値は https://huggingface.co を使う。値全体の URL 妥当性や scheme は検査しない。https://mirror.example/// は https://mirror.example になる一方、ftp://mirror や not a URL も値としては拒否されず、後続の URL 要求に渡る（terminal/setup.py:126-137; terminal/strata_control/pictures.py:72-75; terminal/strata_control/drafting.py:241-249; app/host/server/image-models.mjs:45）。

| 経路 | unset | 有効になる値（例） | 無効・既定値になる値（例） |
|---|---|---|---|
| setup / pictures / drafting / app image models | https://huggingface.co | https://mirror.example、前後に空白があり末尾に /// がある値 → https://mirror.example | 空文字、空白だけ、/// → https://huggingface.co |
| tools/mtp_fetch.py | https://huggingface.co | 前後の空白を除去し、末尾 / を除いた値 | 空文字、空白だけ、/// → 既定値 |
| tools/qwen4_intake.py | https://huggingface.co | https://mirror.example/ → https://mirror.example | 空文字は既定値にならず空の base URL。空白は trim されない |
| tools/quantscope.py | 既定の Hugging Face URL 群 | truthy な値を末尾 / のみ除いて HF URL 群に設定 | unset または空文字は既定 URL 群。空白は trim されない |
| strata_control.transfer._hf_host() | Hugging Face の固定 hostname のみ認識 | strip() 後の値から URL hostname を取り、完全一致する host を認識 | 空白だけ、hostname を取り出せない値はカスタム HF host として認識しない |

ツールごとの差は実装どおりである。mtp_fetch.py はモジュール読込時に正規化済みの定数を作る。qwen4_intake.py は hf_list() / read_hf_entry() の呼び出し時に既定値付きで os.environ.get し、空文字も明示値として残す。quantscope.py はモジュール読込時に設定の truthiness だけを判定し、値全体は trim しない（terminal/tools/mtp_fetch.py:48-51; terminal/tools/qwen4_intake.py:663-679; terminal/tools/quantscope.py:34-44）。

無効な URL 文字列、大小文字、空白、数値、0/1、true/false を endpoint 用の boolean や数値として parse する処理はない。空でない値は URL base として扱う。transfer の host 認識だけは urlparse(...).hostname を使い、ValueError を無視する。このため無効値なら既定 endpoint に戻るのは、各経路で正規化後が空になる場合に限られる（terminal/setup.py:129-132; terminal/strata_control/transfer.py:227-235）。

## 有効になる条件

- setup の --source / STRATA_SOURCE が ModelScope を選ぶと、通常の ModelScope 対応ダウンロードはそちらが優先される。CLI --source は STRATA_SOURCE に設定される。HF_ENDPOINT は source 選択を切り替えない。ModelScope が応答しない場合の警告は hf_endpoint() の値を表示するが、実際の fallback URL は download() に渡された元の URL のままなので、caller が hf_endpoint() で URL を組み立てていない取得経路では endpoint は反映されない。Hugging Face 専用 ready-made pack の URL は hf_endpoint() で組み立てる（terminal/setup.py:212-220, 11536-11539, 11622-11623, 3546-3552, 3947-3948）。
- setup で検証済みファイルがある場合や、同一 SHA-256 の別パックから hard link できる場合、そのファイルは再取得されず endpoint も接続先を変えない（terminal/setup.py:3919-3948, 3513-3519）。
- 通常の GGUF model shard / vision encoder の一部は fam["hf"] / fam["mmproj_hf"] から直接 URL を作るため、この変数でホストを書き換えない（terminal/setup.py:11258-11274, 12408-12430）。
- tools/mtp_fetch.py では STRATA_SOURCE=ms または modelscope が設定されると MODELSCOPE_ENDPOINT から REPO と PINNED を作り直し、HF_ENDPOINT は使われない。--repo は fetch/inventory 用の REPO をさらに上書きする（terminal/tools/mtp_fetch.py:48-57, 521-525; setup からの起動: terminal/setup.py:1160-1165）。
- strata_control.transfer の読み取りは URL 選択用ではなく Bearer 認証対象 host の判定用。固定の Hugging Face host、または HF_ENDPOINT の hostname と一致する host で、HF_TOKEN / HUGGING_FACE_HUB_TOKEN が設定されている場合だけ認証 header を返す。HTTP(S) 以外や一致しない host には返さない（terminal/strata_control/transfer.py:220-251）。
- picture 取得で明示的な endpoint 引数が渡されると、それを使って URL を作り、HF_ENDPOINT は参照しない（terminal/strata_control/pictures.py:72-75, 378-382, 468-475）。
- デスクトップ画像モデル API は library() が返す download URL に endpoint を反映するが、実際のネットワーク取得は real モードの install 経路だけ。シミュレーションではダウンロードしない（app/host/server/image-models.mjs:35-46, 77-91）。
- quantscope.py の差し替えは hf: ソースに対するもの。ms:、直接 URL、ローカルファイルにはこの HF URL 群を使わない（terminal/tools/quantscope.py:34-44, 78-80）。

## 実行時の詳細

setup の hf_endpoint() は呼ぶたびに環境を読み、値を cache しない。ready-made pack の不足ファイル URL、setup の画像生成モデル URL、ModelScope 失敗時の警告表示に使う。ModelScope 失敗時も download() の元 URL が hf_endpoint() 由来でなければ fallback の接続先は変わらない。model_source() は (STRATA_SOURCE, 生の HF_ENDPOINT, MODELSCOPE_ENDPOINT) をキーに結果を辞書 cache するが、source 選択結果は STRATA_SOURCE の ms / modelscope 判定のみで決まる。環境変更後は新しいキーで判定される（terminal/setup.py:129-137, 178-183, 212-220, 3546-3552, 3947-3948, 6003-6008）。

MTP helper は import 時の環境値から REPO / PINNED を一度作るため、同じ Python プロセス内で後から HF_ENDPOINT を変えても URL は変わらない。setup は mtp_fetch.py を子プロセスとして起動し、環境 dict に STRATA_SOURCE を明示し、他の環境変数は継承する（terminal/tools/mtp_fetch.py:48-57; terminal/setup.py:1131-1151, 1160-1165）。Qwen intake は hf_list() と read_hf_entry() ごとに読む。quantscope は import 時に HUBS を作る。pictures と DFlash2 は URL 生成時に読む。transfer の認証判定は各リクエスト生成時に読む。デスクトップ画像モデルは library() 呼び出しごとに URL を生成し、install がその URL を取得する（terminal/tools/qwen4_intake.py:663-679; terminal/tools/quantscope.py:34-44; terminal/strata_control/pictures.py:72-75; terminal/strata_control/drafting.py:244-249; terminal/strata_control/transfer.py:227-251, 303-308, 405-415; app/host/server/image-models.mjs:35-46, 87-91）。

setup の download 経路では、ネットワーク失敗時に host とエラーを含めて cannot reach ... を出し、TLS 証明書問題は cannot download from <host>: its security certificate was not accepted として停止する。ModelScope 選択時の接続失敗 fallback では ModelScope does not answer; downloading it from <HF endpoint> の警告がある（terminal/setup.py:3551-3552, 3573-3581）。picture 取得は接続可能な URL がなければ There is no internet connection, so the picture files can't be downloaded now.、取得失敗なら The picture files could not be downloaded. Try again; it continues where it stopped. のエラー経路に進む（terminal/strata_control/pictures.py:390-408, 470-482）。デスクトップ画像モデルの失敗は API が返す error 状態の error.message に入り、ファイル過大・検証失敗などはコード上のメッセージで報告される（app/host/server/image-models.mjs:91-118）。

## 根拠

- terminal/setup.py:126-137, 173-220, 3513-3581, 3919-3948, 5998-6008, 11536-11539, 11622-11623, 12380-12414 — setup の endpoint 正規化、source 選択、URL 使用、fallback、ログ。
- terminal/strata_control/pictures.py:65-75, 378-408, 455-483 — projector URL と endpoint 引数、取得・失敗経路。
- terminal/strata_control/drafting.py:235-249、terminal/strata_control/drafting_fetch.py:388-412 — DFlash2 URL base と取得。
- terminal/strata_control/transfer.py:220-251, 303-318, 405-420 — endpoint host の認識と HF token header の適用箇所。
- terminal/tools/mtp_fetch.py:43-57, 515-539、terminal/tools/qwen4_intake.py:663-681, 1013-1023、terminal/tools/quantscope.py:34-44, 78-80、terminal/tools/strata_inspect.py:13, 31-33 — 同梱ツールの読み取りと利用条件。
- app/host/server/image-models.mjs:35-46, 64-118、app/host/server/index.mjs:1596-1605 — デスクトップ画像モデル API、実ダウンロードと状態報告。
- docs/SAFETY.md:45 — 利用者向け資料もモデルファイル、picture reader、MTP layer の取得先を Hugging Face または指定 mirror と記載。
