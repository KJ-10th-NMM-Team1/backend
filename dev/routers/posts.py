from fastapi import APIRouter, Query, Depends, HTTPException, status
from typing import Any, List, Optional
from dev.services.post_service import PostService
from dev.model.models import PostOut, PostCreate, User
from dev.services.auth_service import get_current_user
from bson import ObjectId

router = APIRouter(
    prefix='/posts',        # main.py의 /api와 결합 -> /api/posts
    tags=['Posts']
)

# GET /api/posts/
@router.get('/', response_model=List[PostOut])
async def get_post_all(
    sort: Optional[str] = Query(default='createdAt', description='정렬 필드'),
    page: int = Query(1, ge=1), 
    limit: int = Query(10, ge=1, le=100), 
    post_service: PostService = Depends(PostService)):

    posts = await post_service.post_find_all(sort=sort, page=page, limit=limit)
    status_check(posts, status_code=404, message='게시물들을 찾을 수 없습니다.')

    return posts

@router.get('/count', response_model=int)
async def get_post_count(post_service: PostService = Depends(PostService)):
    return await post_service.post_count()


# GET /api/posts/{id}
@router.get('/{id}', response_model=PostOut)
async def get_post_detail(
    id: str,
    post_service: PostService = Depends(PostService)):

    status_check(ObjectId.is_valid(id), status_code=400, message='유효하지 않은 ID 형식입니다.')
    post = await post_service.post_find_one(id)
    status_check(post, status_code=404, message='게시글을 찾을 수 없습니다.')
    return post

# POST /api/posts/
@router.put('/', response_model=PostOut, status_code=status.HTTP_201_CREATED)
async def create_new_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
    post_service: PostService = Depends(PostService)):

    inserted_id = await post_service.post_insert(
        post_data=post_data,
        auth_id=current_user.email,
        auth_name=current_user.username
    )

    created_post = await post_service.post_find_one(inserted_id)
    status_check(created_post, status_code=500, message='글 작성 실패')
    
    return created_post

@router.delete('/{id}', response_model=bool)
async def delete_post(
    id: str, 
    current_user: User = Depends(get_current_user),
    post_service: PostService = Depends(PostService)):
    
    # 2. (검증) ID 형식이 올바른지 확인합니다.
    status_check(ObjectId.is_valid(id), status_code=400, message='유효하지 않은 ID 형식입니다.')

    # 3. 🔑 (인가) 삭제 전에 먼저 게시글을 조회합니다.
    post = await post_service.post_find_one(id)
    
    status_check(post, status_code=404, message='게시글을 찾을 수 없습니다.')
    status_check(post.auth_id == current_user.email, status_code=403, message='삭제 권한이 없습니다.')

    deleted = await post_service.post_delete_one(id)
    
    status_check(deleted, status_code=500, message='삭제에 실패했습니다.')
    return deleted

@router.patch('/{id}', response_model=PostOut)
async def update_post(
    id: str, 
    new_post: PostCreate, 
    current_user: User = Depends(get_current_user),
    post_service: PostService = Depends(PostService)):
     # 2. (검증) ID 형식이 올바른지 확인합니다.
    status_check(ObjectId.is_valid(id), status_code=400, message='유효하지 않은 ID 형식입니다.')

    # 3. 🔑 (인가) 삭제 전에 먼저 게시글을 조회합니다.
    post = await post_service.post_find_one(id)
    
    status_check(post, status_code=404, message='게시글을 찾을 수 없습니다.')
    status_check(post.auth_id == current_user.email, status_code=403, message='수정 권한이 없습니다.')

    updated_id = await post_service.post_update(id, new_post)

    status_check(updated_id, status_code=500, message='수정에 실패했습니다.')
    updated_post = await post_service.post_find_one(id=updated_id)
    return updated_post


def status_check(post: Any, status_code: int, message: str):
    if not post:
        raise HTTPException(status_code=status_code, detail=message)
