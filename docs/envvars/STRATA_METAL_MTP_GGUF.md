# `STRATA_METAL_MTP_GGUF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal backend で `--mtp` が指す runtime (`rt`) ディレクトリに対応するドラフト GGUF のパスを上書きする。`--mtp` を使う経路では、未設定なら runtime ディレクトリの親にある `mtp-q2_0.gguf` を使うが、この変数が設定されていればその文字列をパスとして保存する。CUDA/HIP・SYCL では MTP のロード先を変更せず、サーバーの会話セッション fingerprint に渡す補助パスとしてのみ参照される。`--mtp` 自体が空、または Metal の値が空文字の場合、ドラフターを実際にロードしない経路がある。`engine/metal/src/engine/window.cpp:3705-3722`, `engine/src/core/mtp.cpp:345-354`, `engine/src/program/generate.cpp:13965-13997`, `engine/sycl/src/program/generate.cpp:8144-8176`。

## 値と判定

この変数は `getenv` の設定有無だけを見て、値の構文・ファイル存在・空白・大文字小文字を検証しない。Metal ローダーは値をそのままパスに代入するため、未設定と空文字は異なる。fingerprint 側では `getenv` が未設定または空文字なら helper に空文字を渡し、helper が既定の兄弟 GGUF パスを解決する。

| 経路 | unset | 設定時に使われる値 | 無効・特殊な値 |
|---|---|---|---|
| Metal の MTP ロード | `<rt 親>/mtp-q2_0.gguf` | 空でない文字列をそのまま GGUF パスにする（例: `/models/draft.gguf`） | 空文字は `g_mtp_path` を空にし、後続のロードをスキップする。`0`、`true`、前後空白なども特別扱いせず、文字列どおりのパスとして扱う。存在しない・読めないパスはロード失敗になる。 |
| CUDA/HIP・SYCL の session fingerprint | helper が `<--mtp の親>/mtp-q2_0.gguf` を解決 | 非空文字列を MTP GGUF の候補パスとして helper に渡す | 空文字は未設定と同じ既定パス扱い。MTP が無効なら helper はファイルを列挙しない。 |

Metal の既定パス解決は末尾の `/` を除いて最後の `/` までを親として切り出す。Windows では `window.cpp` の実装にもかかわらず `\` を区切りとして処理する分岐はなく、既定解決は `/` 基準である。上書き値自体は正規化しない。`engine/metal/src/engine/window.cpp:3708-3722`。Fingerprint helper は Windows では `/` と `\` のうち後ろにある区切りを選ぶ。`engine/src/core/conversation_file.cpp:976-989`。

## 有効になる条件

- **Metal で実際の GGUF ロードを変える場合:** Strata が Metal build であり、`--mtp` が残っていて `MtpDrafter::load` が呼ばれ、Metal window の初期化が行われること。Metal `MtpDrafter::load` は `mtp_load(rt_dir, ...)` に渡し、window 初期化時に保留パスをロードする。`engine/src/core/mtp.cpp:345-354`, `engine/metal/src/engine/window.cpp:3627-3638`。
- **`--mtp` が無指定、または CLI の処理でクリアされた場合:** この変数はドラフターのロードを有効化しない。SYCL では `--mtp` があっても `--spec` が 2 未満なら `--mtp` を無視してクリアする。`engine/src/program/generate.cpp:8264`, `engine/sycl/src/program/generate.cpp:4524-4541`。
- **CUDA/HIP・SYCL:** 実 MTP ローダーがこの値を読む箇所は確認できない。`session_identity` が必要になったとき、`--mtp` が空でなく、helper が MTP file list を作る条件に合えば fingerprint の対象パスに影響する。helper は `--mtp` が通常ファイルならそのファイルを採用し、dense/experts pack directory なら pack ファイルを採用して環境変数を使わず、その他の directory は環境変数または既定 sibling GGUF を候補にする。`engine/src/program/generate.cpp:13965-13997`, `engine/sycl/src/program/generate.cpp:8144-8176`, `engine/src/core/conversation_file.cpp:944-997`。
- Metal で空文字を設定した場合、実ロードは空パスのためスキップされる一方、session fingerprint helper に渡る空文字は既定 sibling GGUF に解決される。したがって、fingerprint が表す MTP GGUF と実際にロードされた drafter の状態は一致しない場合がある。また、後続で MTP prefill / draft が呼ばれると `metal mtp: not loaded` で失敗する。`engine/metal/src/engine/window.cpp:3712-3729`, `engine/metal/src/engine/window.cpp:2880-2883`, `engine/metal/src/engine/window.cpp:2930-2933`, `engine/src/program/generate.cpp:13987-13991`, `engine/src/core/conversation_file.cpp:976-990`。

## 実行時の詳細

Metal の `mtp_load` は `getenv` を呼ぶたびに値を読み、環境変数が存在すればその値を `g_mtp_path` に保存する。ここでは GGUF をまだ開かず、`mtp_load_pending` が後の window 初期化で `g_mtp_path` を確認する。空パスなら成功扱いで `Window::mtp_load` を呼ばない。非空なら `Window::mtp_load` が GGUF を開き、Metal buffer として包んでドラフト層を初期化する。値を static cache する実装ではないが、`g_mtp_path` はロード予約時にプロセス内へコピーされるため、その後の環境変更はその予約に反映されない。`engine/metal/src/engine/window.cpp:3705-3729`, `engine/metal/src/engine/window.cpp:2498-2503`, `engine/metal/src/engine/window.cpp:3627-3638`。

非空の不正パスで `fm_.open` が失敗するか、GGUF を Metal buffer に包めない場合は MTP load が失敗する。Metal `MtpDrafter::load` の失敗は `--mtp` の初期化呼び出し元に戻り、`strata generate: <error>` を stderr に出して終了コード 1 で終了する。`engine/metal/src/engine/window.cpp:2498-2503`, `engine/src/core/mtp.cpp:345-354`, `engine/src/program/generate.cpp:8264`。

CUDA/HIP・SYCL の fingerprint 経路では値を呼び出し時に読み、`session_mtp_pack_files` に渡す。同 helper は `--mtp` が空なら即座に空リストを返す。fingerprint 自体は lazy に一度構築・キャッシュされるため、構築後に環境を変更しても既存 fingerprint は更新されない。`engine/src/program/generate.cpp:13965-13997`, `engine/sycl/src/program/generate.cpp:8144-8176`, `engine/src/core/conversation_file.cpp:944-997`。

## ログと測定値

この変数専用の有効・無効ログはない。Metal の失敗時は上記のとおり呼び出し元が error string を stderr に出して終了する。セッション fingerprint がファイルを開けない場合、会話 spill の初期化または保存時にモデル fingerprint 不可の理由を出す経路があるが、環境変数固有の文言ではない。`engine/src/program/generate.cpp:14070-14080`, `engine/src/program/generate.cpp:14110-14118`, `engine/sycl/src/program/generate.cpp:8253-8263`, `engine/sycl/src/program/generate.cpp:8296-8305`。

## 根拠

- Metal の環境値読み取り、既定 sibling path、ロード保留: `engine/metal/src/engine/window.cpp:3705-3729`
- Metal window による GGUF open と失敗: `engine/metal/src/engine/window.cpp:2498-2503`, `engine/metal/src/engine/window.cpp:3627-3638`
- Metal build での MTP load 接続: `engine/src/core/mtp.cpp:345-354`; CUDA/HIP・SYCL での MTP load 呼び出し条件: `engine/src/program/generate.cpp:8264`, `engine/sycl/src/program/generate.cpp:4524-4541`
- CUDA/HIP session fingerprint での環境値読み取りと呼び出し: `engine/src/program/generate.cpp:13965-13997`
- SYCL session fingerprint での環境値読み取りと呼び出し: `engine/sycl/src/program/generate.cpp:8144-8176`
- MTP file list の条件と既定 path 解決: `engine/src/core/conversation_file.cpp:944-997`
